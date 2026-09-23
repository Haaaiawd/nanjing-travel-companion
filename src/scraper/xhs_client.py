"""抓取编排与反爬基础设施。

NoteSource 协议把「渠道」和「编排」分开：FixtureSource 供离线/测试，
WebSource 做真实抓取（限速 + UA 轮换 + cookies + 退避重试）。
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Callable, Protocol

import requests

from .. import config
from .models import Note

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

DEFAULT_KEYWORDS = [
    "南京旅游攻略", "南京美食", "南京拍照", "明孝陵", "中山陵",
    "夫子庙", "老门东", "玄武湖", "总统府", "南京秋天",
]


class AuthError(RuntimeError):
    """cookies 失效 / 触发登录墙。"""


class RateLimiter:
    """最小间隔 + 随机抖动的串行限速器。sleeper/time_fn 可注入以便测试。"""

    def __init__(
        self,
        min_interval: float = 2.0,
        jitter: float = 1.5,
        sleeper: Callable[[float], None] = time.sleep,
        time_fn: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        self.min_interval = min_interval
        self.jitter = jitter
        self._sleep = sleeper
        self._time = time_fn
        self._rng = rng or random.Random()
        self._last = float("-inf")  # 首次调用不等待

    def wait(self) -> float:
        """阻塞到允许下一次请求，返回本次实际等待秒数。"""
        now = self._time()
        gap = now - self._last
        need = self.min_interval + self._rng.uniform(0, self.jitter)
        delay = max(0.0, need - gap)
        if delay > 0:
            self._sleep(delay)
        self._last = self._time()
        return delay


class NoteSource(Protocol):
    def search(self, keyword: str, limit: int) -> list[str]: ...
    def fetch_note(self, note_id: str) -> dict: ...


class FixtureSource:
    """从目录里的 note JSON 文件读数据，供离线开发与测试。"""

    def __init__(self, notes_dir: Path | str) -> None:
        self.notes_dir = Path(notes_dir)

    def _all(self) -> list[dict]:
        return [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(self.notes_dir.glob("*.json"))
        ]

    def search(self, keyword: str, limit: int = 20) -> list[str]:
        hits = []
        for d in self._all():
            hay = " ".join([d.get("title", ""), d.get("text", ""),
                            *d.get("tags", [])])
            if keyword in hay:
                hits.append(d["note_id"])
        return hits[:limit]

    def fetch_note(self, note_id: str) -> dict:
        path = self.notes_dir / f"{note_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))


class WebSource:
    """真实小红书 web 端抓取。

    公开笔记详情页可从 `window.__INITIAL_STATE__` 提取结构化 JSON（需登录 cookies）。
    搜索接口需要 X-S/X-T 签名（JS 生成），纯 requests 无法稳定构造 —— 因此
    search() 从本地关键词→note_id 的 seed 文件读候选，fetch_note() 做真实抓取。
    需要搜索能力时应换 MCPSource 或 playwright 方案。
    """

    EXPLORE_URL = "https://www.xiaohongshu.com/explore/{note_id}"

    def __init__(
        self,
        cookies: str | None = None,
        rate_limiter: RateLimiter | None = None,
        session: requests.Session | None = None,
        seed_file: Path | str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.cookies = cookies if cookies is not None else config.XHS_COOKIES
        self.limiter = rate_limiter or RateLimiter(
            min_interval=1.0 / max(config.SCRAPER_RATE_LIMIT, 0.01), jitter=1.5
        )
        self.session = session or requests.Session()
        self.timeout = timeout
        self._seed = {}
        if seed_file and Path(seed_file).exists():
            self._seed = json.loads(Path(seed_file).read_text(encoding="utf-8"))

    def _headers(self) -> dict:
        h = {
            "User-Agent": random.choice(UA_POOL),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.xiaohongshu.com/",
        }
        if self.cookies:
            h["Cookie"] = self.cookies
        return h

    def _get(self, url: str) -> requests.Response:
        last_exc: Exception | None = None
        for attempt, backoff in enumerate((2, 4, 8)):
            self.limiter.wait()
            try:
                resp = self.session.get(
                    url, headers=self._headers(), timeout=self.timeout
                )
            except requests.RequestException as e:
                last_exc = e
                continue
            if resp.status_code in (401, 403):
                raise AuthError(f"{resp.status_code} on {url} — cookies 可能失效")
            if resp.status_code in (429, 500, 502, 503):
                last_exc = RuntimeError(f"HTTP {resp.status_code}")
                time.sleep(backoff)
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError(f"fetch failed after retries: {url}") from last_exc

    def search(self, keyword: str, limit: int = 20) -> list[str]:
        """签名接口走不通时的务实方案：读本地 seed {keyword: [note_ids]}。"""
        return list(self._seed.get(keyword, []))[:limit]

    def fetch_note(self, note_id: str) -> dict:
        """抓详情页 HTML，从 __INITIAL_STATE__ 提取笔记 JSON。"""
        resp = self._get(self.EXPLORE_URL.format(note_id=note_id))
        return self._parse_initial_state(resp.text, note_id)

    @staticmethod
    def _parse_initial_state(html: str, note_id: str) -> dict:
        marker = "window.__INITIAL_STATE__="
        i = html.find(marker)
        if i < 0:
            raise ValueError(f"__INITIAL_STATE__ not found for {note_id}")
        start = html.find("{", i)
        depth, end = 0, start
        in_str, esc = False, False
        for j in range(start, len(html)):
            c = html[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
        raw = json.loads(html[start:end].replace("undefined", "null"))
        note = raw.get("note", {}).get("noteDetailMap", {}).get(note_id, {})
        return note.get("note", note) if isinstance(note, dict) else {}


class MCPSource:
    """本地 xiaohongshu-mcp 服务（若用户已部署）。接口按常见实现封装。"""

    def __init__(self, base_url: str | None = None,
                 session: requests.Session | None = None,
                 limiter: RateLimiter | None = None) -> None:
        self.base_url = (base_url or config.XHS_MCP_URL).rstrip("/")
        self.session = session or requests.Session()
        self.limiter = limiter or RateLimiter(min_interval=1.0, jitter=0.5)

    def search(self, keyword: str, limit: int = 20) -> list[str]:
        self.limiter.wait()
        resp = self.session.post(
            f"{self.base_url}/api/search",
            json={"keyword": keyword, "limit": limit}, timeout=20,
        )
        resp.raise_for_status()
        items = resp.json().get("notes", [])
        return [n["note_id"] for n in items if "note_id" in n]

    def fetch_note(self, note_id: str) -> dict:
        self.limiter.wait()
        resp = self.session.get(
            f"{self.base_url}/api/notes/{note_id}", timeout=20
        )
        resp.raise_for_status()
        return resp.json()


def normalize_note(raw: dict, note_id_hint: str = "") -> Note:
    """把各 source 的原始 dict 归一成 Note。字段名容忍常见变体。"""
    image_urls = raw.get("image_urls") or raw.get("images") or []
    image_urls = [u for u in image_urls if isinstance(u, str) and u.startswith("http")]
    user = raw.get("user")
    author = raw.get("author") or (
        user.get("nickname", "") if isinstance(user, dict) else ""
    )
    return Note(
        note_id=raw.get("note_id") or raw.get("id") or note_id_hint,
        title=raw.get("title", ""),
        author=author,
        url=raw.get("url")
        or WebSource.EXPLORE_URL.format(
            note_id=raw.get("note_id") or note_id_hint),
        image_urls=image_urls,
        images=list(raw.get("images_local", [])),
        text=raw.get("text") or raw.get("desc", ""),
        tags=[t.lstrip("#") for t in (raw.get("tags") or [])],
        likes=int(raw.get("likes") or raw.get("liked_count") or 0),
        created_at=raw.get("created_at") or raw.get("time", ""),
    )


class XhsScraper:
    """编排：source.search → fetch → normalize → save → 由调用方下载图片。"""

    def __init__(
        self,
        source: NoteSource,
        notes_dir: Path | str = config.RAW_NOTES_DIR,
    ) -> None:
        self.source = source
        self.notes_dir = Path(notes_dir)

    def already_have(self, note_id: str) -> bool:
        return (self.notes_dir / f"{note_id}.json").exists()

    def scrape(self, keywords: list[str] | None = None,
               limit_per_keyword: int = 10,
               skip_existing: bool = True) -> list[Note]:
        keywords = keywords or DEFAULT_KEYWORDS
        seen: set[str] = set()
        notes: list[Note] = []
        for kw in keywords:
            for note_id in self.source.search(kw, limit_per_keyword):
                if note_id in seen or (skip_existing and self.already_have(note_id)):
                    continue
                seen.add(note_id)
                try:
                    raw = self.source.fetch_note(note_id)
                    note = normalize_note(raw, note_id)
                except AuthError:
                    raise
                except Exception:
                    continue  # 单篇失败不阻塞整批
                note.save(self.notes_dir)
                notes.append(note)
        return notes

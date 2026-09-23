"""图片下载器：把 Note.image_urls 落成 data/raw/images/{note_id}_{idx}.{ext}。"""
from __future__ import annotations

import random
import time
from pathlib import Path

import requests

from .. import config
from .models import Note
from .xhs_client import RateLimiter, UA_POOL


_EXT_BY_MIME = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
    "image/gif": ".gif",
}


class ImageDownloader:
    def __init__(
        self,
        images_dir: Path | str = config.RAW_IMAGES_DIR,
        session: requests.Session | None = None,
        limiter: RateLimiter | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.images_dir = Path(images_dir)
        self.session = session or requests.Session()
        self.limiter = limiter or RateLimiter(min_interval=0.5, jitter=0.5)
        self.timeout = timeout

    def _path_for(self, note_id: str, idx: int, url: str, ctype: str = "") -> Path:
        ext = _EXT_BY_MIME.get(ctype.split(";")[0].strip())
        if not ext:
            ext = "." + url.split("?")[0].rsplit(".", 1)[-1].lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                ext = ".jpg"
        return self.images_dir / f"{note_id}_{idx}{ext}"

    def _fetch(self, url: str, headers: dict) -> requests.Response | None:
        """带退避重试的单图抓取。404/4xx 不重试；超时/连接错/5xx 重试两次。"""
        for attempt, backoff in enumerate((0, 1.0, 3.0)):
            if backoff:
                time.sleep(backoff)
            self.limiter.wait()
            try:
                resp = self.session.get(
                    url, headers=headers, timeout=self.timeout, stream=True
                )
            except requests.RequestException:
                continue  # 超时/连接错 → 重试
            if resp.status_code == 404 or 400 <= resp.status_code < 500:
                return None  # 永久失败不重试
            if resp.status_code >= 500:
                continue
            return resp
        return None

    def download(self, note: Note, referer: str = "") -> list[str]:
        """下载 note.image_urls，填充 note.images（本地路径字符串），幂等。"""
        self.images_dir.mkdir(parents=True, exist_ok=True)
        local: list[str] = []
        headers = {
            "User-Agent": random.choice(UA_POOL),
            "Referer": referer or "https://www.xiaohongshu.com/",
        }
        for idx, url in enumerate(note.image_urls):
            existing = sorted(self.images_dir.glob(f"{note.note_id}_{idx}.*"))
            if existing:
                local.append(str(existing[0]))
                continue
            resp = self._fetch(url, headers)
            if resp is None:
                continue  # 单图失败不阻塞
            path = self._path_for(
                note.note_id, idx, url, resp.headers.get("Content-Type", "")
            )
            path.write_bytes(resp.content)
            local.append(str(path))
        note.images = local
        return local

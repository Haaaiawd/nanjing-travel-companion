"""镜像站（6li6）图遍历采集：从种子 view 页出发沿「相关笔记」推荐链
做 best-first 爬取，把命中栖霞区关键词的笔记归一成 Note 落盘。

用法:
    python scripts/mirror_crawl.py --seeds 50883 65101 65541 --max-pages 400
    python scripts/mirror_crawl.py --resume state.json   # 续爬

说明:
    - 镜像页提供: 标题、正文全文、tags、封面图(ci.xiaohongshu.com CDN)、
      原笔记 explore URL(含真实 note_id)、解析时间。
    - 镜像页只暴露封面一张图(与 HARVEST.md B 段一致)。
    - 不登录、不签名；仅 GET 公开镜像页，限速 ~1.4 req/s。
"""
from __future__ import annotations

import argparse
import heapq
import html
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.scraper.models import Note  # noqa: E402
from src.scraper.downloader import ImageDownloader  # noqa: E402

VIEW_URL = "https://6li6.com/xiaohongshu/view-{vid}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# 栖霞区 POI 关键词（强命中 → 笔记算栖霞素材）
STRONG = ["栖霞山", "栖霞寺", "栖霞区", "千佛岩", "千佛崖", "舍利塔",
          "达摩古洞", "幕燕", "燕子矶", "明镜湖", "红叶谷"]
# 语境词（配合判断，避免把烟台栖霞苹果之类收进来）
CONTEXT = ["南京", "栖霞", "红枫", "枫叶", "赏枫", "幕府山", "五马渡"]

_TAG_RE = re.compile(r"#([^#\[\]]{1,40})\[话题\]")
_REL_RE = re.compile(r'href="(/xiaohongshu/view-(\d+))"[^>]*>(.*?)</a>', re.S)
_EXPLORE_RE = re.compile(r"xiaohongshu\.com/explore/([0-9a-zA-Z]{24})")
_TIME_RE = re.compile(r"时间：(\d{4}-\d{2}-\d{2})")


@dataclass
class ViewPage:
    vid: int
    title: str = ""
    desc: str = ""
    tags: list = field(default_factory=list)
    note_id: str = ""
    cover: str = ""
    parsed_at: str = ""          # 镜像记录时间
    related: list = field(default_factory=list)  # [(vid, title)]
    ok: bool = False


def fetch_view(vid: int, session: requests.Session, delay: float = 0.7) -> ViewPage:
    p = ViewPage(vid=vid)
    try:
        r = session.get(VIEW_URL.format(vid=vid), headers={"User-Agent": UA},
                        timeout=20)
        if r.status_code != 200:
            return p
        t = r.text
    except requests.RequestException:
        return p
    finally:
        time.sleep(delay)

    m = re.search(r"<h1[^>]*>(.*?)</h1>", t, re.S)
    p.title = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""

    # 正文 div：h1 之后第一个 lh:2 容器
    m = re.search(r'<div class="mt:2 lh:2[^"]*"[^>]*>(.*?)</div>', t, re.S)
    raw_desc = m.group(1) if m else ""
    p.tags = _TAG_RE.findall(raw_desc)
    desc = _TAG_RE.sub("", raw_desc)
    desc = re.sub(r"<[^>]+>", "", desc)
    p.desc = html.unescape(desc).strip()

    m = _EXPLORE_RE.search(t)
    p.note_id = m.group(1) if m else ""

    m = re.search(r'<img[^>]+src="(https?://ci\.xiaohongshu\.com/[^"]+)"', t)
    if not m:
        m = re.search(r"(https?://ci\.xiaohongshu\.com/[^\s\"']+)", t)
    p.cover = m.group(1).replace("http://", "https://") if m else ""

    m = _TIME_RE.search(t)
    p.parsed_at = m.group(1) if m else ""

    for _path, rvid, rtitle in _REL_RE.findall(t):
        rt = html.unescape(re.sub(r"<[^>]+>", "", rtitle)).strip()
        p.related.append((int(rvid), rt))
    p.ok = bool(p.title or p.desc)
    return p


_TRAVEL = ("攻略", "游", "景点", "打卡", "路线", "小众", "爬山", "徒步",
           "门票", "机位", "拍照", "公园", "古镇", "citywalk")
_SCENE = ("红枫", "枫叶", "赏枫", "银杏", "秋天", "石窟", "寺庙", "古刹",
          "千年", "佛光", "舍利")


def link_priority(title: str) -> int | None:
    """链接标题 → 优先分数(小=优先)；None = 不入队（剪枝）。"""
    if any(k in title for k in STRONG):
        return 0
    nanjing = "南京" in title or "金陵" in title or "栖霞" in title
    if nanjing and any(k in title for k in _TRAVEL + _SCENE):
        return 1
    if nanjing:
        return 2
    if any(k in title for k in _SCENE):
        return 3
    return None


def relevance(p: ViewPage) -> int:
    """命中强度：0=不相关, 1=提及, 2=主题相关。"""
    blob = p.title + p.desc + " ".join(p.tags)
    strong_hits = sum(1 for k in STRONG if k in blob)
    if strong_hits == 0:
        return 0
    # 防误收：烟台栖霞等 —— 要求南京语境或≥2个POI命中或标题命中
    title_hit = any(k in p.title for k in STRONG)
    if title_hit or strong_hits >= 2 or "南京" in blob:
        return 2 if title_hit else 1
    return 0


def page_to_note(p: ViewPage) -> Note:
    return Note(
        note_id=p.note_id,
        title=p.title,
        url=f"https://www.xiaohongshu.com/explore/{p.note_id}",
        image_urls=[p.cover] if p.cover else [],
        text=p.desc,
        tags=p.tags,
        created_at=p.parsed_at,  # 镜像记录时间（原笔记发布时间不可得）
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="*", type=int, default=[50883])
    ap.add_argument("--max-pages", type=int, default=400)
    ap.add_argument("--need", type=int, default=15, help="收够这么多条就收工")
    ap.add_argument("--delay", type=float, default=0.7)
    ap.add_argument("--resume", type=str, default="", help="续爬 state json")
    ap.add_argument("--dry-run", action="store_true", help="只收集不落盘")
    args = ap.parse_args()

    session = requests.Session()
    downloader = ImageDownloader()

    visited: set[int] = set()
    queue: list[tuple[int, int, str]] = []  # (prio, vid, title)
    results: dict[str, ViewPage] = {}     # note_id -> page
    seen_pages: dict[int, ViewPage] = {}

    for vid in args.seeds:
        heapq.heappush(queue, (0, vid, "seed"))
    if args.resume:
        st = json.loads(Path(args.resume).read_text(encoding="utf-8"))
        for it in st.get("queue", []):
            heapq.heappush(queue, (it["prio"], it["vid"], it["title"]))
        visited = set(st.get("visited", []))
        print(f"resume: queue={len(queue)} visited={len(visited)}")

    existing = {f.stem for f in config.RAW_NOTES_DIR.glob("*.json")}
    print(f"已有笔记 {len(existing)} 条（跳过同 note_id）")

    n = 0
    while queue and n < args.max_pages and len(results) < args.need:
        prio, vid, via = heapq.heappop(queue)
        if vid in visited:
            continue
        visited.add(vid)
        n += 1
        p = fetch_view(vid, session, args.delay)
        seen_pages[vid] = p
        rel = relevance(p)
        marker = "★" * rel or " "
        print(f"[{n:3d}] view-{vid} {marker} {p.title[:46]}", flush=True)
        if rel and p.note_id and p.note_id not in existing \
                and p.note_id not in results:
            results[p.note_id] = p
            print(f"      → 收录 #{len(results)} note_id={p.note_id} "
                  f"(via {via[:30]})")
        for rvid, rtitle in p.related:
            if rvid in visited:
                continue
            pr = link_priority(rtitle)
            if pr is not None:
                heapq.heappush(queue, (pr, rvid, rtitle))

    # state dump（可续爬）
    state = {
        "visited": sorted(visited),
        "queue": [{"prio": pr, "vid": v, "title": t} for pr, v, t in queue],
        "matched": {nid: p.vid for nid, p in results.items()},
    }
    Path("data/raw/mirror_crawl_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n爬取 {n} 页, 候选 {len(results)} 条")
    for nid, p in results.items():
        print(f"  {nid}  view-{p.vid}  {p.title[:50]}")

    if args.dry_run:
        return 0

    saved = 0
    for nid, p in results.items():
        note = page_to_note(p)
        if nid in existing:
            continue
        note.save(config.RAW_NOTES_DIR)
        local = downloader.download(note)
        note.save(config.RAW_NOTES_DIR)
        saved += 1
        print(f"  ✓ saved {nid} | {len(local)} 图 | {note.title[:40]}")
    print(f"落盘 {saved} 条 → {config.RAW_NOTES_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

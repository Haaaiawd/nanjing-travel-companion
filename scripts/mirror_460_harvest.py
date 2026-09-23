"""Harvest Xiaohongshu reposts from the b.460.net.cn mirror into Note JSON + images.

b.460.net.cn reposts authentic XHS note bodies (hashtag block, @mentions with
data-user-id / data-xsec-token markup preserved) but strips the original note_id
and rehosts images on img.bim99.cn. We therefore use a mirror-scoped note_id
(`b460_{article_id}`) and record the mirror URL as `url`; provenance details are
documented in data/raw/HARVEST.md.
"""
from __future__ import annotations

import html
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scraper.models import Note  # noqa: E402

NOTES_DIR = ROOT / "data" / "raw" / "notes"
IMG_DIR = ROOT / "data" / "raw" / "images"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"}

JUNK_TAG = re.compile(r"(think|[0-9a-f]{1,6};|;|^'$|^\d+;)", re.I)


def fetch(url: str) -> str:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8", "replace")


def parse_article(aid: int) -> dict:
    t = fetch(f"https://b.460.net.cn/a/{aid}.html")
    m = re.search(r"<h1[^>]*>(.*?)</h1>", t, re.S)
    title = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""
    # mirror exposes no reliable publish time (only a dynamic last-modified
    # span); leave created_at empty and document in HARVEST.md
    created_at = ""
    # body lives in the ...news_con div, ends at the copyright block
    bm = re.search(r'news_con"[^>]*>(.*?)(?:<div class="[^"]*copyright)', t, re.S)
    body = bm.group(1) if bm else ""
    img_urls = list(dict.fromkeys(re.findall(r'(?:src|data-src)="(https?://img\.bim99\.cn/[^"]+?\.(?:webp|jpg|jpeg|png))"', body)))
    text = html.unescape(re.sub(r"<[^>]+>", "\n", body))
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    if text.startswith(title):
        text = text[len(title):].lstrip()
    tags = []
    for tag in re.findall(r"#([^\s#<]{2,30})", text):
        tag = tag.strip("。，,.、!！")
        if tag and not JUNK_TAG.match(tag) and tag not in tags:
            tags.append(tag)
    return {"title": title, "created_at": created_at, "text": text, "tags": tags, "image_urls": img_urls}


def download(url: str, dest: Path) -> bool:
    try:
        data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()
        if len(data) < 500:
            return False
        dest.write_bytes(data)
        return True
    except Exception as e:
        print(f"    img fail {url[:80]}: {e}")
        return False


def harvest(aid: int) -> Note | None:
    try:
        a = parse_article(aid)
    except Exception as e:
        print(f"{aid}: fetch/parse fail {e}")
        return None
    if not a["title"] or len(a["text"]) < 30:
        print(f"{aid}: thin content, skipped")
        return None
    nid = f"b460_{aid}"
    local_imgs = []
    for i, u in enumerate(a["image_urls"]):
        ext = u.rsplit(".", 1)[-1].split("?")[0][:5]
        dest = IMG_DIR / f"{nid}_{i}.{ext}"
        if not dest.exists() and download(u, dest):
            time.sleep(0.3)
        if dest.exists():
            local_imgs.append(str(dest))
    note = Note(
        note_id=nid,
        title=a["title"],
        author="",
        url=f"https://b.460.net.cn/a/{aid}.html",
        image_urls=a["image_urls"],
        images=local_imgs,
        text=a["text"],
        tags=a["tags"],
        likes=0,
        created_at=a["created_at"],
        crawled_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    note.save(NOTES_DIR)
    print(f"{nid}: '{a['title'][:40]}' text={len(a['text'])}c imgs={len(local_imgs)}/{len(a['image_urls'])} tags={len(a['tags'])}")
    return note


if __name__ == "__main__":
    aids = [int(x) for x in sys.argv[1:]]
    ok = sum(1 for a in aids if harvest(a))
    print(f"saved {ok}/{len(aids)}")

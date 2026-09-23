"""镜像站（6li6）时间窗扫描：按 view-id 顺序扫 /xiaohongshu/list-N
列表页，标题/摘要命中关键词时输出候选 view-id。

栖霞山素材集中在红枫季（10-12月），view-id 与解析时间近似线性：
    view-80000  ≈ 2024-09-19     view-160000 ≈ 2025-08-22
    view-95000  ≈ 2024-11-15     view-175000 ≈ 2026-01-20

用法:
    python scripts/mirror_list_scan.py --from-page 3500 --to-page 4300
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from pathlib import Path

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# 强命中（直接候选）
STRONG = ["栖霞", "千佛岩", "千佛崖", "舍利塔", "达摩", "幕燕", "燕子矶",
          "明镜湖", "红叶谷", "始皇临江", "摄山", "栖霞寺"]
# 弱命中（栖霞语境相关，需人工/二次确认）
WEAK = ["红枫", "枫叶", "赏枫", "南京秋", "南京的秋天", "金陵"]

ITEM_RE = re.compile(
    r'<a href="/xiaohongshu/view-(\d+)">.*?'
    r'<div class="title[^"]*">(.*?)</div>\s*<p[^>]*>(.*?)</p>',
    re.S)


def scan_page(page: int, session: requests.Session) -> list[tuple[int, str, str]]:
    url = f"https://6li6.com/xiaohongshu/list-{page}"
    r = session.get(url, headers={"User-Agent": UA}, timeout=20)
    if r.status_code != 200:
        return []
    out = []
    for vid, title, snip in ITEM_RE.findall(r.text):
        t = html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        s = html.unescape(re.sub(r"<[^>]+>", "", snip)).strip()
        out.append((int(vid), t, s))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-page", type=int, required=True)
    ap.add_argument("--to-page", type=int, required=True)
    ap.add_argument("--out", type=str, default="/tmp/list_hits.jsonl")
    ap.add_argument("--delay", type=float, default=0.35)
    args = ap.parse_args()

    s = requests.Session()
    hits = weak = 0
    with open(args.out, "a", encoding="utf-8") as f:
        for pg in range(args.from_page, args.to_page + 1):
            try:
                items = scan_page(pg, s)
            except requests.RequestException:
                items = []
            for vid, t, sn in items:
                blob = t + " " + sn
                if any(k in blob for k in STRONG):
                    hits += 1
                    f.write(json.dumps({"vid": vid, "title": t, "snip": sn,
                                        "page": pg, "level": "strong"},
                                       ensure_ascii=False) + "\n")
                    print(f"  STRONG view-{vid} | {t[:50]}")
                elif any(k in blob for k in WEAK):
                    weak += 1
                    f.write(json.dumps({"vid": vid, "title": t, "snip": sn,
                                        "page": pg, "level": "weak"},
                                       ensure_ascii=False) + "\n")
            if pg % 100 == 0:
                print(f"...page {pg} hits={hits} weak={weak}", flush=True)
            time.sleep(args.delay)
    print(f"done. strong={hits} weak={weak} → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

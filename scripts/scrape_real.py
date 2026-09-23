"""真实抓取入口：MCPSource → normalize → save → ImageDownloader。

用法:
    # 已扫码登录 —— 真搜索
    python scripts/scrape_real.py --mode search --keywords 南京旅游攻略 明孝陵 --limit 15

    # 未登录 —— 游客降级：抓首页推荐流 + 外部 token 清单（可选）
    python scripts/scrape_real.py --mode guest
    python scripts/scrape_real.py --mode guest --tokens tokens.json  # [{id, token, title}]

tokens.json 由频道页 DOM 提取（见 .loom/design/SCRAPER.md 调研节）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.scraper.downloader import ImageDownloader  # noqa: E402
from src.scraper.xhs_client import (MCPSource, XhsScraper,  # noqa: E402
                                    normalize_note)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["search", "guest"], default="search")
    ap.add_argument("--keywords", nargs="*", default=None)
    ap.add_argument("--limit", type=int, default=15, help="每关键词条数")
    ap.add_argument("--tokens", type=str, default="",
                    help="外部 token 清单 JSON: [{id, token, title}]")
    ap.add_argument("--note-ids", nargs="*", default=None,
                    help="只抓这些 note_id（tokens 文件需含其 token）")
    ap.add_argument("--max-images-per-note", type=int, default=9)
    ap.add_argument("--filter", type=str, default="",
                    help="标题/正文正则过滤，命中才保存")
    args = ap.parse_args()

    src = MCPSource()
    print(f"MCP: {src.base_url}")
    try:
        logged = src.is_logged_in()
    except Exception as e:
        print(f"MCP 不可达: {e}")
        return 1
    print(f"登录态: {'已登录' if logged else '未登录(游客)'}")

    scraper = XhsScraper(src, notes_dir=config.RAW_NOTES_DIR)
    downloader = ImageDownloader()

    # -- 登记外部 tokens --------------------------------------------------------
    if args.tokens:
        items = json.loads(Path(args.tokens).read_text(encoding="utf-8"))
        for it in items:
            src.register_token(it.get("id") or it.get("note_id"),
                               it.get("token") or it.get("xsecToken", ""))
        print(f"外部 tokens: {len(items)} 条")

    # -- 收集 note_ids ----------------------------------------------------------
    if args.note_ids:
        plan = [("manual", args.note_ids)]
    elif args.mode == "search":
        if not logged:
            print("未登录：搜索接口对游客关闭（XHS -104）。"
                  "请扫码：python scripts/xhs_login.py")
            return 2
        kws = args.keywords or ["南京旅游攻略", "南京美食", "明孝陵",
                                  "夫子庙", "玄武湖"]
        plan = [(kw, src.search(kw, args.limit)) for kw in kws]
    else:  # guest
        if args.tokens:  # 已给 token 清单 → 直接抓清单里的笔记
            ids = [it.get("id") or it.get("note_id")
                   for it in json.loads(
                       Path(args.tokens).read_text(encoding="utf-8"))]
            plan = [("tokens", [i for i in ids if i])]
        else:
            plan = [("guest_feed", src.list_feeds())]

    total_ids = sum(len(v) for _, v in plan)
    print(f"计划抓取: {total_ids} 篇")

    # -- 抓详情 + 存盘 + 下图 ----------------------------------------------------
    import re
    pat = re.compile(args.filter) if args.filter else None
    saved, skipped, failed = 0, 0, 0
    for label, ids in plan:
        print(f"\n[{label}] {len(ids)} 篇")
        for nid in ids:
            if scraper.already_have(nid):
                skipped += 1
                continue
            try:
                raw = src.fetch_note(nid)
                note = normalize_note(raw, nid)
            except Exception as e:
                print(f"  ✗ {nid}: {e}")
                failed += 1
                continue
            if pat and not (pat.search(note.title) or pat.search(note.text)):
                print(f"  ~ {nid} 不相关，跳过: {note.title[:40]}")
                continue
            note.image_urls = note.image_urls[:args.max_images_per_note]
            note.save(config.RAW_NOTES_DIR)
            local = downloader.download(note)
            note.save(config.RAW_NOTES_DIR)  # images 回填后再存一次
            saved += 1
            print(f"  ✓ {nid} {note.title[:40]} | {note.author} | "
                  f"{note.likes}赞 | {len(local)}/{len(note.image_urls)}图")
            time.sleep(0.5)

    print(f"\n完成: saved={saved} skipped={skipped} failed={failed}")
    print(f"notes → {config.RAW_NOTES_DIR}")
    print(f"images → {config.RAW_IMAGES_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

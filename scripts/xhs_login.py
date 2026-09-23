"""小红书扫码登录助手：拉取 xiaohongshu-mcp 的登录二维码并轮询状态。

用法:
    python scripts/xhs_login.py            # 保存二维码到 .loom/tmp/ 并等待扫码
    python scripts/xhs_login.py --status   # 仅查看登录态
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import config  # noqa: E402


def _get(path: str, timeout: float = 30) -> dict:
    with urllib.request.urlopen(
            f"{config.XHS_MCP_URL}{path}", timeout=timeout) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--wait", type=int, default=240,
                    help="等待扫码秒数（二维码约4分钟有效）")
    args = ap.parse_args()

    st = _get("/api/v1/login/status").get("data", {})
    if st.get("is_logged_in"):
        print(f"已登录: {st.get('username', '')}")
        return 0
    if args.status:
        print("未登录")
        return 1

    qr = _get("/api/v1/login/qrcode", timeout=60).get("data", {})
    img = qr.get("img", "")
    if not img.startswith("data:image"):
        print("未拿到二维码:", qr)
        return 1
    out = ROOT / ".loom" / "tmp" / "xhs_login_qr.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(img.split(",", 1)[1]))
    print(f"二维码已保存: {out}")
    print("请用手机小红书 App → 扫一扫 → 登录")
    print(f"等待中（二维码 {qr.get('timeout', '4m')} 过期）...")

    deadline = time.time() + args.wait
    while time.time() < deadline:
        time.sleep(5)
        try:
            st = _get("/api/v1/login/status").get("data", {})
        except Exception:
            continue
        if st.get("is_logged_in"):
            print(f"\n登录成功: {st.get('username', '')}")
            print("cookies 已持久化在容器卷，以后无需再扫。")
            return 0
        print(".", end="", flush=True)
    print("\n超时未扫码。重新运行本命令可再取一张二维码。")
    return 2


if __name__ == "__main__":
    sys.exit(main())

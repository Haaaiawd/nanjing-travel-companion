"""集中管理路径与环境配置。所有模块共用，不做 provider 选择逻辑。"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data"
RAW_NOTES_DIR = DATA_DIR / "raw" / "notes"
RAW_IMAGES_DIR = DATA_DIR / "raw" / "images"
PROCESSED_DIR = DATA_DIR / "processed"
INDEX_DIR = DATA_DIR / "index"
MOCK_DIR = DATA_DIR / "mock"
MOCK_NOTES_DIR = MOCK_DIR / "notes"
OCR_CACHE_DIR = DATA_DIR / "cache" / "ocr"

CHUNKS_FILE = PROCESSED_DIR / "chunks.json"
GRAPH_FILE = PROCESSED_DIR / "knowledge_graph.json"
EMBEDDINGS_FILE = INDEX_DIR / "embeddings.json"
SEARCH_INDEX_FILE = INDEX_DIR / "search_index.json"


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _load_dotenv() -> None:
    """极简 .env 加载：仅在变量未设置时补充，不依赖第三方库。"""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

# --- 百炼 / DashScope（OpenAI 兼容端点） ---
DASHSCOPE_API_KEY = env("DASHSCOPE_API_KEY")
DASHSCOPE_BASE_URL = env(
    "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
EMBEDDING_MODEL = env("EMBEDDING_MODEL", "qwen3.7-text-embedding-flash")
COMPANION_MODEL = env("COMPANION_MODEL", "qwen-turbo")
COMPANION_TEMPERATURE = float(env("COMPANION_TEMPERATURE", "0.8"))

# --- 视觉理解（默认 AI Ping 平台的豆包，OpenAI 兼容） ---
VL_API_KEY = env("VL_API_KEY")
VL_BASE_URL = env("VL_BASE_URL", "https://aiping.cn/api/v1")
VL_MODEL = env("VL_MODEL", "doubao-2.1-pro")

# --- Scraper ---
XHS_COOKIES = env("XHS_COOKIES")
SCRAPER_RATE_LIMIT = float(env("SCRAPER_RATE_LIMIT", "0.5"))  # 请求/秒
XHS_MCP_URL = env("XHS_MCP_URL", "http://localhost:18060")

# --- Knowledge ---
TOP_K_RETRIEVAL = int(env("TOP_K_RETRIEVAL", "5"))


def ensure_dirs() -> None:
    for d in (RAW_NOTES_DIR, RAW_IMAGES_DIR, PROCESSED_DIR, INDEX_DIR,
              MOCK_NOTES_DIR, OCR_CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)

"""共享 fixtures：全部测试离线运行，外部服务一律 mock。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.knowledge.embeddings import HashEmbedding          # noqa: E402
from src.knowledge.graph import KnowledgeGraph              # noqa: E402
from src.knowledge.indexer import build_index               # noqa: E402
from src.knowledge.schema import Chunk                      # noqa: E402

MOCK_DIR = ROOT / "data" / "mock"


@pytest.fixture(scope="session")
def mock_notes_dir() -> Path:
    return MOCK_DIR / "notes"


@pytest.fixture(scope="session")
def mock_chunks() -> list[Chunk]:
    raw = json.loads((MOCK_DIR / "chunks.json").read_text(encoding="utf-8"))
    return [Chunk.from_dict(d) for d in raw]


@pytest.fixture(scope="session")
def mock_graph(mock_chunks) -> KnowledgeGraph:
    return KnowledgeGraph.build(mock_chunks)


@pytest.fixture(scope="session")
def mock_index(mock_chunks):
    return build_index(mock_chunks, HashEmbedding())

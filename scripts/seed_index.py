"""从 mock/ocr 产出的 chunks 构建知识库索引。

用法：.venv/bin/python scripts/seed_index.py [--chunks data/mock/chunks.json]
无 API key 时自动用 HashEmbedding，可离线运行。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.knowledge.embeddings import make_default_provider
from src.knowledge.graph import KnowledgeGraph
from src.knowledge.indexer import (build_index, load_chunks, save_chunks,
                                   save_index)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default=str(config.MOCK_DIR / "chunks.json"),
                    help="chunk 来源（mock 或 ocr 产物）")
    args = ap.parse_args()

    chunks = load_chunks(args.chunks)
    save_chunks(chunks, config.CHUNKS_FILE)

    graph = KnowledgeGraph.build(chunks)
    graph.save(config.GRAPH_FILE)

    provider = make_default_provider()
    index = build_index(chunks, provider)
    save_index(index, config.INDEX_DIR)

    print(f"chunks: {len(chunks)} -> {config.CHUNKS_FILE}")
    print(f"graph locations: {len(graph.locations)} -> {config.GRAPH_FILE}")
    print(f"index: {len(index.vectors)} vectors -> {config.INDEX_DIR}")
    print(f"provider: {type(provider).__name__} (dim={provider.dim or 'n/a'})")


if __name__ == "__main__":
    main()

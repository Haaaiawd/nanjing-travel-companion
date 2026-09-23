"""索引构建与加载：本地 JSON + 内存暴力扫描，demo 规模足够。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .. import config
from .embeddings import EmbeddingProvider
from .schema import Chunk


@dataclass
class Index:
    chunks: dict[str, Chunk]                # chunk_id -> Chunk
    vectors: dict[str, list[float]]         # chunk_id -> vector
    by_location: dict[str, list[str]]       # location -> [chunk_id]
    by_type: dict[str, list[str]]
    by_tag: dict[str, list[str]]

    def candidates_for(self, poi: str | None) -> list[str]:
        if poi and poi in self.by_location:
            return list(self.by_location[poi])
        return list(self.chunks)


def _inverted(chunks: list[Chunk]) -> tuple[dict, dict, dict]:
    by_loc: dict[str, list[str]] = {}
    by_type: dict[str, list[str]] = {}
    by_tag: dict[str, list[str]] = {}
    for c in chunks:
        locs = {c.location, *(c.structured_data.get("locations") or [])}
        for loc in locs:
            by_loc.setdefault(loc, []).append(c.chunk_id)
        by_type.setdefault(c.type, []).append(c.chunk_id)
        for t in c.tags:
            by_tag.setdefault(t, []).append(c.chunk_id)
    return by_loc, by_type, by_tag


def build_index(chunks: list[Chunk],
                provider: EmbeddingProvider) -> Index:
    """整库重建：批量 embed → 内存 Index。"""
    vectors: dict[str, list[float]] = {}
    texts = [c.embed_text() for c in chunks]
    embs = provider.embed(texts)
    if len(embs) != len(chunks):
        raise RuntimeError(
            f"embedding count mismatch: {len(embs)} vs {len(chunks)}")
    for c, v in zip(chunks, embs):
        vectors[c.chunk_id] = v
    by_loc, by_type, by_tag = _inverted(chunks)
    return Index(
        chunks={c.chunk_id: c for c in chunks},
        vectors=vectors,
        by_location=by_loc,
        by_type=by_type,
        by_tag=by_tag,
    )


def save_index(index: Index, index_dir: Path | str = config.INDEX_DIR) -> None:
    d = Path(index_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / "embeddings.json").write_text(
        json.dumps(index.vectors, ensure_ascii=False), encoding="utf-8")
    (d / "search_index.json").write_text(
        json.dumps({"by_location": index.by_location,
                    "by_type": index.by_type,
                    "by_tag": index.by_tag}, ensure_ascii=False, indent=2),
        encoding="utf-8")


def load_index(index_dir: Path | str = config.INDEX_DIR,
               chunks_file: Path | str = config.CHUNKS_FILE) -> Index:
    d = Path(index_dir)
    vectors = json.loads((d / "embeddings.json").read_text(encoding="utf-8"))
    inv = json.loads((d / "search_index.json").read_text(encoding="utf-8"))
    chunk_list = [Chunk.from_dict(x) for x in
                  json.loads(Path(chunks_file).read_text(encoding="utf-8"))]
    return Index(
        chunks={c.chunk_id: c for c in chunk_list},
        vectors={k: [float(x) for x in v] for k, v in vectors.items()},
        by_location=inv["by_location"],
        by_type=inv["by_type"],
        by_tag=inv["by_tag"],
    )


def load_chunks(path: Path | str = config.CHUNKS_FILE) -> list[Chunk]:
    return [Chunk.from_dict(x)
            for x in json.loads(Path(path).read_text(encoding="utf-8"))]


def save_chunks(chunks: list[Chunk],
                path: Path | str = config.CHUNKS_FILE) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps([c.to_dict() for c in chunks], ensure_ascii=False, indent=2),
        encoding="utf-8")

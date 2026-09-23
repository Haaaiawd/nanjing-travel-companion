"""knowledge 测试：chunk schema、embedding、索引、检索、图谱。"""
from __future__ import annotations

import json

from src.knowledge.embeddings import HashEmbedding, cosine
from src.knowledge.graph import KnowledgeGraph
from src.knowledge.indexer import (build_index, load_chunks, load_index,
                                   save_chunks, save_index)
from src.knowledge.retriever import Retriever
from src.knowledge.schema import Chunk


def test_chunk_schema_roundtrip(mock_chunks):
    c = mock_chunks[0]
    d = c.to_dict()
    for key in ("location", "type", "content", "tags", "structured_data",
                "source_ref"):
        assert key in d
    assert Chunk.from_dict(d).to_dict() == d
    assert "明孝陵" in c.embed_text()


def test_hash_embedding_semantic():
    emb = HashEmbedding(dim=128)
    a, b, c = emb.embed(["明孝陵石象路秋天", "明孝陵秋天拍照", "番茄炒蛋做法"])
    assert cosine(a, b) > cosine(a, c)      # 共享子串的更相似
    assert abs(cosine(a, a) - 1.0) < 1e-6   # 归一化
    assert emb.embed(["same"])[0] == emb.embed(["same"])[0]  # 确定性


def test_index_build_save_load(tmp_path, mock_chunks):
    index = build_index(mock_chunks, HashEmbedding())
    assert len(index.vectors) == len(mock_chunks)
    assert "明孝陵" in index.by_location
    assert "美食" in index.by_type

    chunks_file = tmp_path / "chunks.json"
    save_chunks(mock_chunks, chunks_file)
    save_index(index, tmp_path)
    loaded = load_index(tmp_path, chunks_file)
    assert set(loaded.chunks) == set(index.chunks)
    assert loaded.by_location["夫子庙"]


def test_graph_aliases_nearby_and_build(mock_graph):
    g = mock_graph
    assert g.normalize("石象路") == "明孝陵"
    assert g.normalize("南博") == "南京博物院"
    assert "中山陵" in g.nearby("明孝陵")
    assert g.match_pois("石象路怎么去") == ["明孝陵"]
    # 同笔记 co-occurrence：mix_001 里出现的 POI 互认 nearby
    assert set(g.locations["夫子庙"]["nearby"]) & {"老门东", "玄武湖"}


def test_retriever_poi_query(mock_index, mock_graph):
    r = Retriever(mock_index, mock_graph, HashEmbedding())
    res = r.retrieve("明孝陵怎么玩", top_k=3)
    assert res, "empty retrieval"
    assert res[0].chunk.location == "明孝陵"
    assert "中山陵" in res[0].nearby or "美龄宫" in res[0].nearby


def test_retriever_type_and_alias(mock_index, mock_graph):
    r = Retriever(mock_index, mock_graph, HashEmbedding())
    # 别名：石象路 → 明孝陵
    res = r.retrieve("石象路拍照好看吗", top_k=3)
    assert res[0].chunk.location == "明孝陵"
    # 类型过滤：美食
    res_food = r.retrieve("老门东有什么好吃的", top_k=3, type_filter="美食")
    assert res_food and all(c.chunk.type == "美食" for c in res_food)
    # 季节过滤：秋天
    res_autumn = r.retrieve("南京秋天去哪", top_k=5, season="秋")
    assert res_autumn
    assert any("秋" in " ".join(c.chunk.tags +
               [c.chunk.structured_data.get("time_hint", "")])
               for c in res_autumn)


def test_retriever_no_poi_falls_back(mock_index, mock_graph):
    r = Retriever(mock_index, mock_graph, HashEmbedding())
    res = r.retrieve("随便聊聊南京", top_k=3)
    assert len(res) == 3  # 无 POI → 全库召回


def test_mock_data_covers_required_pois(mock_chunks):
    covered = {c.location for c in mock_chunks}
    for poi in ("明孝陵", "夫子庙", "老门东", "玄武湖", "总统府"):
        assert poi in covered, f"missing mock POI: {poi}"

"""agent 测试：场景识别、PRISMIX prompt 三层、端到端搭子口吻。"""
from __future__ import annotations

from src.agent.companion import Companion
from src.agent.llm import MockLLM
from src.agent.prompt import build_system, render_knowledge
from src.agent.scenes import detect
from src.knowledge.embeddings import HashEmbedding
from src.knowledge.retriever import Retriever


def _companion(mock_index, mock_graph):
    r = Retriever(mock_index, mock_graph, HashEmbedding())
    return Companion(r, MockLLM(), mock_graph)


def test_scene_detect_poi_and_overlay(mock_graph):
    s = detect("明孝陵怎么玩", mock_graph)
    assert s.pois == ["明孝陵"] and s.name == "poi_play"
    s2 = detect("夫子庙有啥好吃的", mock_graph)
    assert s2.pois == ["夫子庙"] and s2.type_filter == "美食"
    s3 = detect("老门东有什么坑要避雷", mock_graph)
    assert s3.name == "pitfall" and s3.type_filter == "避坑"
    s4 = detect("南京秋天去哪拍照", mock_graph)
    assert s4.season == "秋天"


def test_prompt_three_layers(mock_graph, mock_index):
    r = Retriever(mock_index, mock_graph, HashEmbedding())
    chunks = r.retrieve("明孝陵怎么玩", pois=["明孝陵"])
    system = build_system(detect("明孝陵怎么玩", mock_graph), chunks)
    # L1 人设
    assert "金陵搭子" in system and "没去过南京" in system
    # L2 注入的攻略内容 + 克制规则
    assert "我刷到的攻略" in system and "挑 1–2 个" in system
    assert any(c.chunk.content[:8] in system for c in chunks)
    # L3 场景指令
    assert "poi_play" in system


def test_prompt_empty_knowledge_honesty():
    system = render_knowledge([])
    assert "没刷到" in system


def test_end_to_end_companion(mock_index, mock_graph):
    comp = _companion(mock_index, mock_graph)
    result = comp.ask("明孝陵怎么玩？")
    # 检索到了明孝陵 chunk
    assert result.retrieved
    assert result.retrieved[0].chunk.location == "明孝陵"
    # MockLLM 回复引用了检索内容且保持搭子口吻
    assert "我刷到" in result.reply
    assert "也没去过" in result.reply or "没去过" in result.reply
    # prompt 里确实注入了知识
    system = comp.llm.recorded[0][0]["content"]
    assert result.retrieved[0].chunk.content[:10] in system
    # 历史被维护
    assert len(comp.history) == 2


def test_companion_unknown_query_honest(mock_index, mock_graph):
    comp = _companion(mock_index, mock_graph)
    # 过滤到不存在的类型组合 + 无 POI → 仍兜底全库，有回复
    result = comp.ask("南极怎么去？")
    assert result.reply


def test_multi_turn_history(mock_index, mock_graph):
    comp = _companion(mock_index, mock_graph)
    comp.ask("明孝陵怎么玩")
    comp.ask("那夫子庙呢")
    assert len(comp.history) == 4
    last_system = comp.llm.recorded[-1][0]["content"]
    assert "夫子庙" in last_system

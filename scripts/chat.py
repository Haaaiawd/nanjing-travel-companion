"""CLI 对话 demo：.venv/bin/python scripts/chat.py

无 API key 时用 MockLLM + HashEmbedding 跑通全流程；有 DASHSCOPE_API_KEY
时自动切真实 qwen 模型。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.agent.companion import Companion
from src.agent.llm import ChatClient, MockLLM
from src.knowledge.embeddings import make_default_provider
from src.knowledge.graph import KnowledgeGraph
from src.knowledge.indexer import load_index
from src.knowledge.retriever import Retriever


def build_companion() -> Companion:
    index = load_index()
    graph = (KnowledgeGraph.load(config.GRAPH_FILE)
             if config.GRAPH_FILE.exists() else KnowledgeGraph())
    provider = make_default_provider()
    llm = ChatClient() if config.DASHSCOPE_API_KEY else MockLLM()
    return Companion(Retriever(index, graph, provider), llm, graph)


def main() -> None:
    comp = build_companion()
    print("金陵搭子上线（输入 q 退出）")
    while True:
        try:
            text = input("你：").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text or text.lower() == "q":
            break
        result = comp.ask(text)
        print(f"搭子：{result.reply}\n")


if __name__ == "__main__":
    main()

"""Companion：主流程编排。输入 → 场景 → 检索 → prompt → LLM → 回复。"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..knowledge.graph import KnowledgeGraph
from ..knowledge.retriever import Retriever
from ..knowledge.schema import RetrievedChunk
from . import prompt as P
from .scenes import Scene, detect

HISTORY_LIMIT = 6  # 保留最近 3 轮（user+assistant 各算一条）


@dataclass
class TurnResult:
    reply: str
    scene: Scene
    retrieved: list[RetrievedChunk] = field(default_factory=list)


class Companion:
    def __init__(
        self,
        retriever: Retriever,
        llm,
        graph: KnowledgeGraph | None = None,
        top_k: int = 5,
    ) -> None:
        self.retriever = retriever
        self.llm = llm
        self.graph = graph or retriever.graph
        self.top_k = top_k
        self.history: list[dict] = []

    def ask(self, text: str) -> TurnResult:
        scene = detect(text, self.graph)
        retrieved = self.retriever.retrieve(
            text, top_k=self.top_k,
            type_filter=scene.type_filter, season=scene.season,
            pois=scene.pois,
        )
        system = P.build_system(scene, retrieved)
        messages = P.build_messages(system, self.history[-HISTORY_LIMIT:], text)
        reply = self.llm.chat(messages)
        self.history += [{"role": "user", "content": text},
                         {"role": "assistant", "content": reply}]
        return TurnResult(reply=reply, scene=scene, retrieved=retrieved)

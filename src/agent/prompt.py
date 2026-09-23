"""PRISMIX 三层 prompt 组装。

L1 stable core            — persona.py 的人设，永远在最前
L2 environment adaptation — 检索到的 chunks 渲染为「我刷到的攻略」+ 注入规则
L3 capability modules     — 场景命中的行为指令（scenes.detect 给出）
"""
from __future__ import annotations

from ..knowledge.schema import RetrievedChunk
from .persona import PERSONA_CORE
from .scenes import Scene

_INJECT_RULES = (
    "规则：挑 1–2 个最相关的点用自己的话自然带出，像在跟朋友分享刷到的帖子；"
    "不要逐条复述，不要把所有片段都讲完。"
)
_EMPTY_RULES = "你还没刷到跟这个相关的攻略，老实说没刷到，别编。"


def render_knowledge(chunks: list[RetrievedChunk]) -> str:
    """L2：把检索结果渲染成「我刷到的攻略」段落。"""
    if not chunks:
        return f"【我刷到的攻略】\n（空）\n{_EMPTY_RULES}"
    lines = ["【我刷到的攻略】（都是别人的经验，不是你的亲身经历）"]
    for r in chunks:
        c = r.chunk
        src = c.source_ref.get("note_title", "小红书笔记")
        lines.append(f"- [{c.location}·{c.type}] {c.content}（来源：{src}）")
        if r.nearby:
            lines.append(f"  （附近还有：{'、'.join(r.nearby)}，看情况可以提一嘴）")
    lines.append(_INJECT_RULES)
    return "\n".join(lines)


def build_system(scene: Scene, chunks: list[RetrievedChunk]) -> str:
    """三层组装成完整 system prompt。"""
    return "\n\n".join([
        PERSONA_CORE,                        # L1
        render_knowledge(chunks),            # L2
        f"【当前场景】{scene.name}：{scene.instruction}",  # L3
    ])


def build_messages(system: str, history: list[dict],
                   user_text: str) -> list[dict]:
    """system + 最近若干轮历史 + 当前 user。"""
    msgs = [{"role": "system", "content": system}]
    msgs.extend(history)
    msgs.append({"role": "user", "content": user_text})
    return msgs

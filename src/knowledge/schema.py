"""知识库核心 schema：Chunk 是模块间流通的唯一货币。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

CHUNK_TYPES = {"POI", "美食", "路线", "避坑", "住宿", "交通", "其他"}


@dataclass
class Chunk:
    chunk_id: str
    location: str
    type: str
    content: str
    source_note_id: str = ""
    tags: list[str] = field(default_factory=list)
    structured_data: dict = field(default_factory=dict)
    source_ref: dict = field(default_factory=dict)
    confidence: float = 0.9
    created_at: str = ""

    def __post_init__(self) -> None:
        if self.type not in CHUNK_TYPES:
            self.type = "其他"
        if not self.created_at:
            self.created_at = date.today().isoformat()

    def embed_text(self) -> str:
        """结构化字段拍平进 embedding 文本，让 POI 名/tag 参与语义匹配。"""
        parts = [self.location, self.type, *self.tags, self.content]
        return " ".join(p for p in parts if p)

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "source_note_id": self.source_note_id,
            "location": self.location,
            "type": self.type,
            "content": self.content,
            "tags": list(self.tags),
            "structured_data": dict(self.structured_data),
            "source_ref": dict(self.source_ref),
            "confidence": self.confidence,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Chunk":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class RetrievedChunk:
    """检索返回：chunk + 相关度分数 + 可选的 nearby 扩展。"""
    chunk: Chunk
    score: float
    nearby: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = self.chunk.to_dict()
        d["score"] = round(self.score, 4)
        d["nearby"] = self.nearby
        return d

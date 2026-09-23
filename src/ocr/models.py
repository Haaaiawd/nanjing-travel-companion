"""ocr 模块数据模型：ImageInsight（单图理解结果）与 ChunkDraft（产出草稿）。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ImageInsight:
    """一张手帐图的结构化理解结果。"""

    locations: list[str] = field(default_factory=list)
    activities: list[str] = field(default_factory=list)
    time_hint: str = ""
    food: list[str] = field(default_factory=list)
    tips: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    scene_type: str = "其他"          # POI|美食|路线|避坑|住宿|交通|其他
    summary: str = ""
    confidence: float = 0.9

    def to_dict(self) -> dict:
        return {
            "locations": self.locations,
            "activities": self.activities,
            "time_hint": self.time_hint,
            "food": self.food,
            "tips": self.tips,
            "tags": self.tags,
            "scene_type": self.scene_type,
            "summary": self.summary,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ImageInsight":
        def _list(v):
            return [str(x) for x in v] if isinstance(v, list) else []

        known_types = {"POI", "美食", "路线", "避坑", "住宿", "交通", "其他"}
        scene_type = str(d.get("scene_type", "其他"))
        return cls(
            locations=_list(d.get("locations")),
            activities=_list(d.get("activities")),
            time_hint=str(d.get("time_hint", "") or ""),
            food=_list(d.get("food")),
            tips=_list(d.get("tips")),
            tags=_list(d.get("tags")),
            scene_type=scene_type if scene_type in known_types else "其他",
            summary=str(d.get("summary", "") or ""),
            confidence=float(d.get("confidence", 0.9) or 0.0),
        )


@dataclass
class ChunkDraft:
    """ocr → knowledge 的中间产物，字段与 Chunk 契约对齐。"""
    source_note_id: str
    location: str
    type: str
    content: str
    tags: list[str] = field(default_factory=list)
    structured_data: dict = field(default_factory=dict)
    source_image: str | None = None
    confidence: float = 0.9

    def to_dict(self) -> dict:
        return {
            "source_note_id": self.source_note_id,
            "source_image": self.source_image,
            "location": self.location,
            "type": self.type,
            "content": self.content,
            "tags": list(self.tags),
            "structured_data": dict(self.structured_data),
            "confidence": self.confidence,
        }

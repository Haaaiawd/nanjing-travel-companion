"""OCR 编排：Note → ChunkDraft[]。

每张图：缓存命中直接用；否则 VL 理解 → 失败走 PaddleOCR 降级 →
仍失败跳过。正文若有信息量也独立成 chunk。多 location 拆成多条。
"""
from __future__ import annotations

import logging
from pathlib import Path

from ..scraper.models import Note
from .cache import OCRCache, image_key
from .models import ChunkDraft, ImageInsight
from .paddle_fallback import PaddleFallback, structure_text

log = logging.getLogger(__name__)

_TEXT_MIN_LEN = 30  # 正文短于这个长度不值得单独成 chunk


class OCRPipeline:
    def __init__(
        self,
        vl,                               # VLClient | MockVLClient | 任何有 understand() 的对象
        cache: OCRCache | None = None,
        fallback: PaddleFallback | None = None,
    ) -> None:
        self.vl = vl
        self.cache = cache or OCRCache()
        self.fallback = fallback or PaddleFallback()

    def understand_image(self, image_path: Path | str) -> ImageInsight | None:
        """单图理解：cache → VL → paddle 降级 → None。"""
        path = Path(image_path)
        if not path.exists():
            log.warning("image missing: %s", path)
            return None
        key = image_key(path)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        try:
            insight = self.vl.understand(path)
        except Exception as e:
            log.warning("VL failed on %s: %s", path.name, e)
            insight = None
        if (insight is None or insight.confidence <= 0) and self.fallback.available:
            text = self.fallback.extract_text(path)
            if text.strip():
                insight = structure_text(text)
        if insight is None:
            return None
        self.cache.set(key, insight)
        return insight

    def _drafts_from_insight(
        self, note: Note, image: str, insight: ImageInsight
    ) -> list[ChunkDraft]:
        if insight.confidence <= 0:
            return []
        content = insight.summary
        if insight.tips:
            content += "。贴士：" + "；".join(insight.tips)
        structured = {
            "locations": insight.locations,
            "activities": insight.activities,
            "time_hint": insight.time_hint,
            "food": insight.food,
            "tips": insight.tips,
        }
        locations = insight.locations or ["南京"]
        return [
            ChunkDraft(
                source_note_id=note.note_id,
                source_image=image,
                location=loc,
                type=insight.scene_type,
                content=content,
                tags=insight.tags,
                structured_data=structured,
                confidence=insight.confidence,
            )
            for loc in locations
        ]

    def _draft_from_text(self, note: Note) -> ChunkDraft | None:
        text = note.text.strip()
        if len(text) < _TEXT_MIN_LEN:
            return None
        insight = structure_text(text, confidence=0.6)
        return ChunkDraft(
            source_note_id=note.note_id,
            source_image=None,
            location=insight.locations[0] if insight.locations else "南京",
            type=insight.scene_type,
            content=text[:500],
            tags=list(dict.fromkeys(insight.tags + note.tags)),
            structured_data={
                "locations": insight.locations,
                "activities": insight.activities,
                "time_hint": insight.time_hint,
                "food": insight.food,
                "tips": insight.tips,
            },
            confidence=insight.confidence,
        )

    def process_note(self, note: Note) -> list[ChunkDraft]:
        drafts: list[ChunkDraft] = []
        for img in note.images:
            insight = self.understand_image(img)
            if insight is not None:
                drafts.extend(self._drafts_from_insight(note, img, insight))
        text_draft = self._draft_from_text(note)
        if text_draft:
            drafts.append(text_draft)
        return drafts

    def process_notes(self, notes: list[Note]) -> list[ChunkDraft]:
        drafts: list[ChunkDraft] = []
        for n in notes:
            drafts.extend(self.process_note(n))
        return drafts

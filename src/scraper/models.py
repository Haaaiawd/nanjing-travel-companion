"""scraper 数据模型：Note 是 scraper 的产出，也是下游 ocr 的输入。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Note:
    note_id: str
    title: str
    image_urls: list[str] = field(default_factory=list)   # 原始 CDN url
    images: list[str] = field(default_factory=list)        # 本地相对/绝对路径
    text: str = ""
    tags: list[str] = field(default_factory=list)
    likes: int = 0
    created_at: str = ""
    author: str = ""
    url: str = ""
    crawled_at: str = ""

    def __post_init__(self) -> None:
        if not self.crawled_at:
            self.crawled_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def to_dict(self) -> dict:
        return {
            "note_id": self.note_id,
            "title": self.title,
            "author": self.author,
            "url": self.url,
            "image_urls": list(self.image_urls),
            "images": list(self.images),
            "text": self.text,
            "tags": list(self.tags),
            "likes": self.likes,
            "created_at": self.created_at,
            "crawled_at": self.crawled_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Note":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})

    def save(self, notes_dir: Path) -> Path:
        notes_dir.mkdir(parents=True, exist_ok=True)
        path = notes_dir / f"{self.note_id}.json"
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    @classmethod
    def load(cls, path: Path) -> "Note":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

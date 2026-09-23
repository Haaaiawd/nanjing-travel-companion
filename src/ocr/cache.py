"""图片理解结果缓存：key = 图片内容 sha256，避免重复调用模型。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .. import config
from .models import ImageInsight


def image_key(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class OCRCache:
    def __init__(self, cache_dir: Path | str = config.OCR_CACHE_DIR) -> None:
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    def _file(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str) -> ImageInsight | None:
        f = self._file(key)
        if f.exists():
            self.hits += 1
            return ImageInsight.from_dict(json.loads(f.read_text(encoding="utf-8")))
        self.misses += 1
        return None

    def set(self, key: str, insight: ImageInsight) -> None:
        self._file(key).write_text(
            json.dumps(insight.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def stats(self) -> dict:
        return {"hits": self.hits, "misses": self.misses}

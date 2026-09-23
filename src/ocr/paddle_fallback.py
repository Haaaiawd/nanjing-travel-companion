"""PaddleOCR 降级路径：可选导入，缺失不 break 构建。

VL 失败时：paddleocr 提取纯文字 → structure_text() 启发式结构化。
"""
from __future__ import annotations

import re
from pathlib import Path

from .models import ImageInsight

try:
    from paddleocr import PaddleOCR  # type: ignore
    _HAS_PADDLE = True
except Exception:  # ImportError / 环境缺依赖都算不可用
    PaddleOCR = None  # type: ignore
    _HAS_PADDLE = False

# 常见 POI/季节/场景词，降级结构化的召回靠它
_KNOWN_LOCS = [
    "明孝陵", "中山陵", "石象路", "美龄宫", "夫子庙", "秦淮河", "老门东",
    "玄武湖", "总统府", "鸡鸣寺", "南京博物院", "牛首山", "红山动物园",
    "颐和路", "新街口", "大报恩寺", "栖霞山", "阅江楼",
]
_SCENE_RULES = [
    ("避坑", ["坑", "避雷", "踩雷", "别去", "劝退"]),
    ("美食", ["吃", "美食", "小吃", "鸭血粉丝", "汤包", "锅贴"]),
    ("路线", ["路线", "行程", "Day", "天", "安排"]),
    ("住宿", ["住", "酒店", "民宿"]),
    ("交通", ["地铁", "公交", "打车", "机场", "高铁"]),
]


class PaddleFallback:
    def __init__(self) -> None:
        self._ocr = None

    @property
    def available(self) -> bool:
        return _HAS_PADDLE

    def _engine(self):
        if self._ocr is None and _HAS_PADDLE:
            self._ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        return self._ocr

    def extract_text(self, image_path: Path | str) -> str:
        engine = self._engine()
        if engine is None:
            return ""
        result = engine.ocr(str(image_path), cls=True)
        lines = []
        for page in result or []:
            for box in page or []:
                if box and len(box) >= 2 and box[1]:
                    lines.append(str(box[1][0]))
        return "\n".join(lines)


def structure_text(text: str, confidence: float = 0.5) -> ImageInsight:
    """把 OCR 纯文本启发式切成 ImageInsight。质量低于 VL，confidence 打折。"""
    locations = [loc for loc in _KNOWN_LOCS if loc in text]
    tips = [ln.strip() for ln in text.splitlines()
            if re.search(r"(建议|注意|记得|别|提前|避开|一定)", ln)][:5]
    tags = [t for t in ("春天", "夏天", "秋天", "冬天", "夜景", "拍照", "清晨")
            if t in text]
    scene_type = "其他"
    for t, kws in _SCENE_RULES:
        if any(k in text for k in kws):
            scene_type = t
            break
    return ImageInsight(
        locations=locations,
        tips=tips,
        tags=tags,
        scene_type=scene_type,
        summary=text.splitlines()[0][:60] if text.strip() else "",
        confidence=confidence if text.strip() else 0.0,
    )

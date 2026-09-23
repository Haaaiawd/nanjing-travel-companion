"""视觉理解 client：OpenAI 兼容端点（默认 AI Ping 豆包），+ 离线 Mock。

真实调用：POST {base_url}/chat/completions，message 为
[image_url(data-uri), text(prompt)]，要求模型只回 JSON。
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Callable

import requests

from .. import config
from .models import ImageInsight

UNDERSTAND_PROMPT = """这是一张小红书南京旅游攻略的手帐风图片。请识别图中的文字和排版信息，只输出一个 JSON 对象（不要输出任何其他文字）：
{
  "locations": ["图中提到的地点/POI"],
  "activities": ["推荐的活动，如 拍照/散步/看日落"],
  "time_hint": "推荐时间（季节/时段），没有则空字符串",
  "food": ["提到的美食/店铺"],
  "tips": ["实用贴士/避坑建议"],
  "tags": ["内容标签，如 秋天/夜景/汉服"],
  "scene_type": "POI|美食|路线|避坑|住宿|交通|其他 之一",
  "summary": "用一句话口语化总结这张图在推荐什么"
}"""


def parse_insight_json(text: str) -> ImageInsight:
    """宽容解析模型输出：```json 围栏 → 首尾花括号切片 → 失败给 confidence=0。"""
    candidates = []
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        candidates.append(fence.group(1))
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidates.append(text[start:end + 1])
    for c in candidates:
        try:
            return ImageInsight.from_dict(json.loads(c))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return ImageInsight(confidence=0.0, summary=text[:80])


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


class VLClient:
    """OpenAI 兼容的视觉模型 client。默认 AI Ping + doubao-2.1-pro。"""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = (base_url or config.VL_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else config.VL_API_KEY
        self.model = model or config.VL_MODEL
        self.session = session or requests.Session()
        self.timeout = timeout

    def build_payload(self, image_path: Path | str) -> dict:
        return {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": _data_uri(Path(image_path))}},
                    {"type": "text", "text": UNDERSTAND_PROMPT},
                ],
            }],
            "temperature": 0.2,
        }

    def understand(self, image_path: Path | str) -> ImageInsight:
        resp = self.session.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=self.build_payload(image_path),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        return parse_insight_json(text)


class MockVLClient:
    """离线 VL：按图片文件名查表返回 ImageInsight，或走 fallback 函数。

    fixtures: {文件名: insight_dict}；未命中时调用 fallback(path) 或返回
    confidence=0 的空 insight。
    """

    def __init__(
        self,
        fixtures: dict[str, dict] | None = None,
        fallback: Callable[[Path], ImageInsight] | None = None,
    ) -> None:
        self.fixtures = fixtures or {}
        self.fallback = fallback
        self.calls: list[str] = []

    def understand(self, image_path: Path | str) -> ImageInsight:
        path = Path(image_path)
        self.calls.append(path.name)
        if path.name in self.fixtures:
            return ImageInsight.from_dict(self.fixtures[path.name])
        if self.fallback:
            return self.fallback(path)
        return ImageInsight(confidence=0.0)

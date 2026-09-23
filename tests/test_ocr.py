"""ocr 测试：VL payload/解析、缓存去重、pipeline 拆 chunk、降级路径。"""
from __future__ import annotations

import json
from pathlib import Path

from src.ocr.cache import OCRCache, image_key
from src.ocr.models import ImageInsight
from src.ocr.paddle_fallback import PaddleFallback, structure_text
from src.ocr.pipeline import OCRPipeline
from src.ocr.vl_client import MockVLClient, VLClient, parse_insight_json
from src.scraper.models import Note


def _img(tmp_path: Path, name: str, body: bytes = b"jpeg") -> Path:
    p = tmp_path / name
    p.write_bytes(body)
    return p


def test_parse_insight_json_fenced_and_bare():
    fenced = '前言\n```json\n{"locations":["明孝陵"],"scene_type":"POI","summary":"秋天去"}\n```\n后语'
    ins = parse_insight_json(fenced)
    assert ins.locations == ["明孝陵"] and ins.scene_type == "POI"
    bare = parse_insight_json('{"locations":["玄武湖"],"summary":"日落"}')
    assert bare.locations == ["玄武湖"]
    bad = parse_insight_json("完全不是json的输出")
    assert bad.confidence == 0.0


def test_vl_payload_is_openai_compatible(tmp_path):
    img = _img(tmp_path, "a.jpg")
    vl = VLClient(base_url="http://x/v1", api_key="k", model="doubao-2.1-pro")
    payload = vl.build_payload(img)
    msg = payload["messages"][0]
    assert payload["model"] == "doubao-2.1-pro"
    kinds = [c["type"] for c in msg["content"]]
    assert kinds == ["image_url", "text"]
    assert msg["content"][0]["image_url"]["url"].startswith(
        "data:image/jpeg;base64,")


def test_pipeline_splits_locations_and_caches(tmp_path):
    img = _img(tmp_path, "n1_0.jpg", b"img-bytes")
    fixtures = {"n1_0.jpg": {
        "locations": ["明孝陵", "中山陵"], "activities": ["拍照"],
        "time_hint": "10月中下旬", "food": [], "tips": ["8点前到"],
        "tags": ["秋天"], "scene_type": "POI", "summary": "石象路秋天封神"}}
    vl = MockVLClient(fixtures)
    cache = OCRCache(tmp_path / "cache")
    pipe = OCRPipeline(vl, cache=cache)
    note = Note(note_id="n1", title="t", images=[str(img)], text="短")

    drafts = pipe.process_note(note)
    assert len(drafts) == 2                     # 多 location 拆 chunk
    assert {d.location for d in drafts} == {"明孝陵", "中山陵"}
    assert drafts[0].structured_data["tips"] == ["8点前到"]
    assert "8点前到" in drafts[0].content       # tips 拼进 content

    # 第二张相同内容图（不同文件名）→ 缓存命中，VL 不再调用
    img2 = _img(tmp_path, "other_0.jpg", b"img-bytes")
    note2 = Note(note_id="n2", title="t2", images=[str(img2)])
    pipe.process_note(note2)
    assert vl.calls == ["n1_0.jpg"]             # 只调了一次
    assert cache.stats()["hits"] == 1


def test_pipeline_text_chunk_and_missing_image(tmp_path):
    vl = MockVLClient({})
    pipe = OCRPipeline(vl, cache=OCRCache(tmp_path / "c"))
    long_text = "明孝陵的攻略说早上八点前到石象路人少景美，银杏黄的时候随便拍都出片"
    note = Note(note_id="n3", title="t", images=["/nonexistent/x.jpg"],
                text=long_text)
    drafts = pipe.process_note(note)
    assert len(drafts) == 1                     # 图缺失 → 只出正文 chunk
    assert drafts[0].source_image is None
    assert drafts[0].location == "明孝陵"       # structure_text 识别出 POI


def test_vl_failure_falls_back_and_never_raises(tmp_path):
    class BoomVL:
        def understand(self, p):
            raise RuntimeError("api down")

    img = _img(tmp_path, "n4_0.jpg", b"bytes4")
    pipe = OCRPipeline(BoomVL(), cache=OCRCache(tmp_path / "c2"),
                       fallback=PaddleFallback())
    note = Note(note_id="n4", title="t", images=[str(img)])
    drafts = pipe.process_note(note)            # 不抛异常
    assert drafts == []                         # paddle 不可用 → 跳过该图


def test_structure_text_heuristics():
    ins = structure_text("夫子庙夜游记得提前预约画舫，别在正街买小吃")
    assert "夫子庙" in ins.locations
    assert ins.scene_type in ("避坑", "美食")   # 「别」触发避坑或「小吃」触发美食
    assert any("预约" in t or "别" in t for t in ins.tips)
    assert PaddleFallback().available in (True, False)  # 可选导入不 break

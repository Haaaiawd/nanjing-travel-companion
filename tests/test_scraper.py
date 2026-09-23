"""scraper 测试：Note 序列化、限速器、FixtureSource、抓取编排、下载器。"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from src.scraper.downloader import ImageDownloader
from src.scraper.models import Note
from src.scraper.xhs_client import (AuthError, FixtureSource, RateLimiter,
                                    UA_POOL, WebSource, XhsScraper,
                                    normalize_note)


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.t += s


def test_note_roundtrip_schema(tmp_path):
    n = Note(note_id="x1", title="南京攻略", image_urls=["http://a/1.jpg"],
             text="正文", tags=["南京"], likes=42, created_at="2025-01-01")
    d = n.to_dict()
    for key in ("note_id", "title", "images", "text", "tags", "likes",
                "created_at"):
        assert key in d
    assert Note.from_dict(d).to_dict() == d
    path = n.save(tmp_path)
    assert Note.load(path).note_id == "x1"


def test_rate_limiter_enforces_interval():
    clock = FakeClock()
    limiter = RateLimiter(min_interval=2.0, jitter=0.0,
                          sleeper=clock.sleep, time_fn=clock.time)
    limiter.wait()           # 首次不等
    assert clock.slept == []
    limiter.wait()           # 距上次 0s → 补满 2s
    assert clock.slept == [2.0]
    limiter.wait()
    assert clock.slept == [2.0, 2.0]


def test_rate_limiter_jitter_within_bounds():
    clock = FakeClock()
    limiter = RateLimiter(min_interval=1.0, jitter=2.0,
                          sleeper=clock.sleep, time_fn=clock.time,
                          rng=random.Random(7))
    for _ in range(5):
        limiter.wait()
    assert all(1.0 <= s <= 3.0 for s in clock.slept)


def test_fixture_source_search_and_fetch(mock_notes_dir):
    src = FixtureSource(mock_notes_dir)
    ids = src.search("明孝陵", 10)
    assert "xhs_mxl_001" in ids
    raw = src.fetch_note("xhs_fzm_001")
    assert raw["title"].startswith("夫子庙")


def test_scraper_end_to_end_fixture(tmp_path, mock_notes_dir):
    scraper = XhsScraper(FixtureSource(mock_notes_dir), notes_dir=tmp_path)
    notes = scraper.scrape(keywords=["南京旅游", "明孝陵", "夫子庙"],
                           limit_per_keyword=10)
    assert len(notes) >= 3
    ids = {n.note_id for n in notes}
    assert "xhs_mxl_001" in ids and "xhs_fzm_001" in ids
    saved = json.loads((tmp_path / "xhs_mxl_001.json").read_text("utf-8"))
    assert saved["tags"] == ["南京旅游", "明孝陵", "秋天", "拍照"]
    # 幂等：再跑一遍不重复抓
    again = scraper.scrape(keywords=["明孝陵"], limit_per_keyword=10)
    assert again == []


def test_normalize_note_variants():
    raw = {"id": "n9", "title": "t", "desc": "正文",
           "user": {"nickname": "小熊"}, "liked_count": "88",
           "images": ["https://cdn/x.jpg", "notaurl", 5],
           "tags": ["#南京", "攻略"]}
    n = normalize_note(raw)
    assert n.note_id == "n9" and n.author == "小熊" and n.likes == 88
    assert n.image_urls == ["https://cdn/x.jpg"]
    assert n.tags == ["南京", "攻略"]


class _FakeResp:
    def __init__(self, body=b"img", ctype="image/jpeg", status=200,
                 text=""):
        self.content = body
        self.headers = {"Content-Type": ctype}
        self.status_code = status
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class _FakeSession:
    def __init__(self, resp):
        self.resp = resp
        self.calls: list[dict] = []

    def get(self, url, headers=None, timeout=None, stream=False):
        self.calls.append({"url": url, "headers": headers})
        return self.resp


def test_downloader_writes_local_and_idempotent(tmp_path):
    session = _FakeSession(_FakeResp(b"fakejpeg", "image/jpeg"))
    dl = ImageDownloader(images_dir=tmp_path, session=session,
                         limiter=RateLimiter(0, 0, sleeper=lambda s: None))
    note = Note(note_id="n1", title="t",
                image_urls=["https://cdn/x/1.jpg", "https://cdn/x/2"])
    local = dl.download(note)
    assert len(local) == 2
    assert (tmp_path / "n1_0.jpg").read_bytes() == b"fakejpeg"
    # 幂等：文件已存在 → 不再请求
    dl.download(note)
    assert len(session.calls) == 2


def test_websource_headers_rotate_and_cookie():
    src = WebSource(cookies="a1=b2", session=_FakeSession(_FakeResp()))
    h = src._headers()
    assert h["User-Agent"] in UA_POOL
    assert h["Cookie"] == "a1=b2"


def test_websource_auth_error_no_retry():
    session = _FakeSession(_FakeResp(status=403))
    src = WebSource(cookies="x=y", session=session,
                    rate_limiter=RateLimiter(0, 0, sleeper=lambda s: None))
    with pytest.raises(AuthError):
        src.fetch_note("n1")
    assert len(session.calls) == 1  # 403 不重试

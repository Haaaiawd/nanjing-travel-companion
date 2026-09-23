"""scraper 测试：Note 序列化、限速器、FixtureSource、抓取编排、下载器。"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from src.scraper.downloader import ImageDownloader
from src.scraper.models import Note
from src.scraper.xhs_client import (AuthError, FixtureSource, MCPSource,
                                    RateLimiter, UA_POOL, WebSource,
                                    XhsScraper, _mcp_note_to_raw,
                                    _parse_count, normalize_note)


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


# --- MCPSource（xpzouying/xiaohongshu-mcp HTTP API） ---------------------------


class _MCPFakeSession:
    """按 URL 返回预置 JSON 的假 session。"""

    def __init__(self, routes: dict):
        self.routes = routes
        self.calls: list[dict] = []

    def request(self, method, url, timeout=None, **kw):
        self.calls.append({"method": method, "url": url, "kw": kw})
        for key, payload in self.routes.items():
            if key in url:
                return _JsonResp(payload)
        return _JsonResp({"error": "not found", "code": "404"}, status=404)


class _JsonResp:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def json(self):
        return self.payload


def _mcp(routes) -> MCPSource:
    return MCPSource(base_url="http://mcp.test",
                     session=_MCPFakeSession(routes),
                     limiter=RateLimiter(0, 0, sleeper=lambda s: None))


_SEARCH_PAYLOAD = {
    "success": True,
    "data": {"feeds": [
        {"id": "n1", "xsecToken": "tok1",
         "noteCard": {"displayTitle": "南京攻略"}},
        {"id": "n2", "xsecToken": "tok2",
         "noteCard": {"displayTitle": "明孝陵"}},
    ], "count": 2},
}

_DETAIL_PAYLOAD = {
    "success": True,
    "data": {"feed_id": "n1", "data": {"note": {
        "noteId": "n1", "title": "南京3天2晚攻略",
        "desc": "正文 #南京旅游[话题]# #明孝陵[话题]#",
        "time": 1758000000000, "ipLocation": "江苏",
        "user": {"nickname": "金陵玩家"},
        "interactInfo": {"likedCount": "1.2万"},
        "imageList": [{"urlDefault": "http://cdn/1.jpg"},
                      {"urlDefault": "http://cdn/2.jpg"}],
    }}},
}


def test_mcp_search_caches_tokens():
    src = _mcp({"/api/v1/feeds/search": _SEARCH_PAYLOAD})
    ids = src.search("南京旅游", 10)
    assert ids == ["n1", "n2"]
    assert src._tokens == {"n1": "tok1", "n2": "tok2"}
    call = src.session.calls[0]
    assert call["method"] == "GET" and "search" in call["url"]
    assert call["kw"]["params"] == {"keyword": "南京旅游"}


def test_mcp_fetch_note_uses_detail_api():
    src = _mcp({"/api/v1/feeds/search": _SEARCH_PAYLOAD,
                "/api/v1/feeds/detail": _DETAIL_PAYLOAD})
    src.search("南京", 10)
    raw = src.fetch_note("n1")
    body = src.session.calls[-1]["kw"]["json"]
    assert body["feed_id"] == "n1" and body["xsec_token"] == "tok1"
    note = normalize_note(raw)
    assert note.title == "南京3天2晚攻略" and note.author == "金陵玩家"
    assert note.text == "正文"
    assert note.tags == ["南京旅游", "明孝陵"]
    assert note.likes == 12000
    assert note.image_urls == ["http://cdn/1.jpg", "http://cdn/2.jpg"]


def test_mcp_fetch_note_without_token_fails():
    src = _mcp({})
    with pytest.raises(ValueError, match="xsec_token"):
        src.fetch_note("nope")


def test_mcp_search_unlogged_returns_empty():
    src = _mcp({"/api/v1/feeds/search":
                {"success": True, "data": {"feeds": [], "count": 0}}})
    assert src.search("南京", 10) == []


def test_mcp_list_feeds_guest():
    src = _mcp({"/api/v1/feeds/list": _SEARCH_PAYLOAD})
    ids = src.list_feeds()
    assert ids == ["n1", "n2"] and src._tokens["n1"] == "tok1"


def test_parse_count_variants():
    assert _parse_count("1.7万") == 17000
    assert _parse_count("10万+") == 100000
    assert _parse_count("4695") == 4695
    assert _parse_count("") == 0


def test_mcp_note_to_raw_shape():
    raw = _mcp_note_to_raw(_DETAIL_PAYLOAD["data"]["data"]["note"], "n1")
    for key in ("note_id", "title", "desc", "author", "image_urls",
                    "tags", "created_at", "url"):
        assert key in raw
    assert raw["url"].endswith("/explore/n1")


@pytest.mark.skipif(
    __import__("os").environ.get("XHS_LIVE") != "1",
    reason="真实抓取需 XHS_LIVE=1 且 MCP 已扫码登录")
def test_mcp_live_search_and_detail():
    """手动验收：XHS_LIVE=1 pytest -k live。需服务已登录。"""
    src = MCPSource()  # 默认 config.XHS_MCP_URL
    assert src.is_logged_in(), "MCP 未登录 — 先扫码"
    ids = src.search("南京旅游攻略", 5)
    assert ids, "登录后搜索应返回结果"
    raw = src.fetch_note(ids[0])
    note = normalize_note(raw)
    assert note.title and note.image_urls

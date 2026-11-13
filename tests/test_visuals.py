import pytest

from src.gen import visuals


def test_pick_video_link():
    files = [
        {"link": "a", "width": 540, "height": 960},
        {"link": "b", "width": 1080, "height": 1920},
    ]
    assert visuals.pick_video_link(files) == "b"
    assert visuals.pick_video_link(files[:1]) == "a"
    assert visuals.pick_video_link([{"width": 1080}, {"link": "z"}]) == "z"
    assert visuals.pick_video_link([]) is None
    assert visuals.pick_video_link(None) is None


def test_filter_videos():
    vids = [{"duration": 2}, {"duration": 3}, {"duration": 20}, {}, {"duration": "x"}]
    assert visuals.filter_videos(vids) == [{"duration": 3}, {"duration": 20}]
    assert visuals.filter_videos(vids, 3, 10) == [{"duration": 3}]
    assert visuals.filter_videos(None) == []


class FakeResp:
    def __init__(self, payload=None, chunks=()):
        self._payload, self._chunks = payload, chunks

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload

    def iter_content(self, chunk_size=0):
        return iter(self._chunks)


def test_search_uses_timeout_and_filters(monkeypatch):
    monkeypatch.setattr(visuals, "PEXELS_API_KEY", "k")
    seen = {}

    def fake_get(url, **kw):
        seen.update(kw)
        return FakeResp({"videos": [{"duration": 1}, {"duration": 9, "url": "u"}]})

    monkeypatch.setattr(visuals.requests, "get", fake_get)
    out = visuals.search_pexels_videos("cat")
    assert out == [{"duration": 9, "url": "u"}]
    assert seen["timeout"] == visuals.REQUEST_TIMEOUT
    assert seen["headers"] == {"Authorization": "k"}


def test_search_without_key(monkeypatch):
    monkeypatch.setattr(visuals, "PEXELS_API_KEY", None)
    assert visuals.search_pexels_videos("cat") == []


def test_search_network_error(monkeypatch):
    monkeypatch.setattr(visuals, "PEXELS_API_KEY", "k")

    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(visuals.requests, "get", boom)
    assert visuals.search_pexels_videos("cat") == []


def test_download_video(monkeypatch, tmp_path):
    monkeypatch.setattr(
        visuals.requests, "get", lambda *a, **k: FakeResp(chunks=[b"ab", b"", b"cd"])
    )
    out = visuals.download_video("http://x", tmp_path / "sub" / "v.mp4")
    assert (tmp_path / "sub" / "v.mp4").read_bytes() == b"abcd"
    assert out.endswith("v.mp4")


def _stock(monkeypatch, tmp_path, search):
    calls = []

    def fake_search(q, *a, **k):
        calls.append(q)
        return search(q)

    monkeypatch.setattr(visuals, "search_pexels_videos", fake_search)
    monkeypatch.setattr(visuals, "download_video", lambda url, out: f"dl:{url}")
    return calls


def test_stock_footage_skips_used(monkeypatch, tmp_path):
    vids = [
        {"url": "p1", "video_files": [{"link": "l1"}]},
        {"url": "p2", "video_files": [{"link": "l2"}]},
    ]
    _stock(monkeypatch, tmp_path, lambda q: vids)
    path, url = visuals.get_stock_footage("a b", "o.mp4", used_urls={"p1"})
    assert (path, url) == ("dl:l2", "p2")


def test_stock_footage_reuses_when_all_used(monkeypatch, tmp_path):
    vids = [{"url": "p1", "video_files": [{"link": "l1"}]}]
    _stock(monkeypatch, tmp_path, lambda q: vids)
    assert visuals.get_stock_footage("a", "o.mp4", used_urls={"p1"}) == ("dl:l1", "p1")


def test_stock_footage_fallback_chain(monkeypatch, tmp_path):
    calls = _stock(monkeypatch, tmp_path, lambda q: [])
    assert visuals.get_stock_footage("dark deep ocean", "o.mp4") == (None, None)
    assert calls == ["dark deep ocean", "ocean", "abstract background"]


def test_stock_footage_no_files(monkeypatch, tmp_path):
    _stock(monkeypatch, tmp_path, lambda q: [{"url": "p", "video_files": []}])
    assert visuals.get_stock_footage("a", "o.mp4") == (None, None)

import asyncio
import sys
import types

import pytest


@pytest.fixture
def td(monkeypatch):
    fake = types.ModuleType("yt_dlp")
    fake.calls = []
    fake.info = {"entries": []}
    fake.fail_download = False

    class YDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            fake.calls.append(("info", url, self.opts))
            if isinstance(fake.info, Exception):
                raise fake.info
            return fake.info

        def download(self, urls):
            if fake.fail_download:
                raise RuntimeError("blocked")
            fake.calls.append(("download", urls, self.opts))
            with open(self.opts["outtmpl"], "wb") as f:
                f.write(b"v")

    fake.YoutubeDL = YDL
    monkeypatch.setitem(sys.modules, "yt_dlp", fake)
    sys.modules.pop("src.sources.tiktok_downloader", None)
    import src.sources.tiktok_downloader as mod

    mod.fake = fake
    yield mod
    sys.modules.pop("src.sources.tiktok_downloader", None)


def test_clean_username(td):
    c = td.clean_username
    assert c("@foo") == "foo"
    assert c(" foo ") == "foo"
    assert c("https://www.tiktok.com/@foo/video/123?x=1") == "foo"
    assert c("") == "" and c(None) == ""


def test_get_user_videos_builds_url_and_limits(td):
    td.fake.info = {"entries": [{"id": "1"}, None, {"id": "2"}]}
    out = td.TikTokDownloader().get_user_videos_sync("@bar", count="3")
    assert out == [{"id": "1"}, {"id": "2"}]
    kind, url, opts = td.fake.calls[0]
    assert url == "https://www.tiktok.com/@bar" and opts["playlist_items"] == "1-3"


def test_get_user_videos_failure_modes(td):
    d = td.TikTokDownloader()
    assert d.get_user_videos_sync("") == []
    td.fake.info = None
    assert d.get_user_videos_sync("x") == []
    td.fake.info = RuntimeError("net")
    assert d.get_user_videos_sync("x") == []


def test_download_video_async(td, tmp_path):
    d = td.TikTokDownloader()
    out = str(tmp_path / "a.mp4")
    assert asyncio.run(d.download_video({"url": "http://v"}, out)) is True
    assert asyncio.run(d.download_video({}, out)) is False
    td.fake.fail_download = True
    assert asyncio.run(d.download_video({"url": "http://v"}, str(tmp_path / "b.mp4"))) is False


def test_sync_channel_skips_existing(td, tmp_path):
    td.fake.info = {"entries": [{"id": "1", "url": "u1"}, {"id": "2", "url": "u2"}, {"nope": 1}]}
    (tmp_path / "bar_1.mp4").write_bytes(b"old")
    asyncio.run(td.TikTokDownloader().sync_channel("@bar", str(tmp_path), count=3))
    downloads = [c for c in td.fake.calls if c[0] == "download"]
    assert [c[1] for c in downloads] == [["u2"]]
    assert (tmp_path / "bar_2.mp4").exists()

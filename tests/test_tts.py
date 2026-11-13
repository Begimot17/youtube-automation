import asyncio

import pytest

from src.gen import tts


class FakeCommunicate:
    instances = []

    def __init__(self, text, voice):
        self.text, self.voice = text, voice
        FakeCommunicate.instances.append(self)

    async def save(self, path):
        with open(path, "wb") as f:
            f.write(b"mp3")


@pytest.fixture(autouse=True)
def fake_edge(monkeypatch):
    FakeCommunicate.instances = []
    monkeypatch.setattr(tts.edge_tts, "Communicate", FakeCommunicate)


def test_default_voice_by_language(tmp_path):
    tts.generate_voiceover("hi", tmp_path / "a" / "o.mp3", lang="ru")
    tts.generate_voiceover("hi", tmp_path / "o2.mp3", lang="en")
    tts.generate_voiceover("hi", tmp_path / "o3.mp3", lang="de")
    assert [i.voice for i in FakeCommunicate.instances] == [
        "ru-RU-SvetlanaNeural", "en-US-AriaNeural", "en-US-AriaNeural"]


def test_explicit_voice_and_file_written(tmp_path):
    out = tts.generate_voiceover("hi", tmp_path / "o.mp3", voice="x")
    assert out == tmp_path / "o.mp3" and out.read_bytes() == b"mp3"
    assert FakeCommunicate.instances[0].voice == "x"


def test_empty_text(tmp_path):
    assert tts.generate_voiceover("  ", tmp_path / "o.mp3") is None
    assert tts.generate_voiceover(None, tmp_path / "o.mp3") is None


def test_failure_returns_none(tmp_path, monkeypatch):
    class Boom(FakeCommunicate):
        async def save(self, path):
            raise RuntimeError("net")

    monkeypatch.setattr(tts.edge_tts, "Communicate", Boom)
    assert tts.generate_voiceover("hi", tmp_path / "o.mp3") is None


def test_works_inside_running_loop(tmp_path):
    pytest.importorskip("nest_asyncio")

    async def inner():
        return tts.generate_voiceover("hi", tmp_path / "o.mp3")

    assert asyncio.run(inner()) == tmp_path / "o.mp3"

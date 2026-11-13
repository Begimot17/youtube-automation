import base64

import pytest

from src.gen_v2 import main as g


class Resp:
    def __init__(self, payload=None, content=b""):
        self.payload, self.content = payload, content

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(g.time, "sleep", lambda s: None)


def feed(monkeypatch, statuses):
    it = iter(statuses)
    monkeypatch.setattr(g.requests, "get", lambda *a, **k: Resp(next(it)))


def test_poll_completes_and_returns_output(monkeypatch):
    feed(monkeypatch, [{"status": "IN_QUEUE"}, {"status": "IN_PROGRESS"},
                       {"status": "COMPLETED", "output": {"url": "x"}}])
    assert g.poll_job("j", "u", {}) == {"url": "x"}


def test_poll_completed_without_output(monkeypatch):
    feed(monkeypatch, [{"status": "COMPLETED", "output": None}])
    assert g.poll_job("j", "u", {}) == {}


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED", "TIMED_OUT"])
def test_poll_fails_fast_on_terminal_failures(monkeypatch, status):
    feed(monkeypatch, [{"status": status, "error": "bad gpu"}])
    with pytest.raises(RuntimeError, match=f"{status}.*bad gpu"):
        g.poll_job("j", "u", {})


def test_poll_times_out(monkeypatch):
    monkeypatch.setattr(g, "MAX_POLL_SECONDS", -1)
    with pytest.raises(TimeoutError):
        g.poll_job("j", "u", {})


def test_save_output_base64(tmp_path):
    out = tmp_path / "o.bin"
    data = base64.b64encode(b"hello").decode()
    g._save_output({"images": ["junk", {"data": data}]}, str(out))
    assert out.read_bytes() == b"hello"


def test_save_output_url(monkeypatch, tmp_path):
    monkeypatch.setattr(g.requests, "get", lambda *a, **k: Resp(content=b"vid"))
    out = tmp_path / "o.bin"
    g._save_output({"message": "https://x/y.mp4"}, str(out))
    assert out.read_bytes() == b"vid"


@pytest.mark.parametrize("bad", [{}, {"message": "not-a-url"}, None, "str", []])
def test_save_output_unparseable(bad, tmp_path):
    with pytest.raises(ValueError):
        g._save_output(bad, str(tmp_path / "o"))

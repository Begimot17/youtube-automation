import pytest

from src.utils import notifications as n


class Resp:
    def __init__(self, fail=False):
        self.fail = fail

    def raise_for_status(self):
        if self.fail:
            raise RuntimeError("500")


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(n, "TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setattr(n, "TELEGRAM_CHAT_ID", "42")


def test_truncate_message():
    assert n.truncate_message("abc") == "abc"
    out = n.truncate_message("x" * 5000)
    assert len(out) == n.TELEGRAM_MAX_LEN and out.endswith("…")


def test_skipped_when_not_configured(monkeypatch):
    monkeypatch.setattr(n, "TELEGRAM_BOT_TOKEN", None)
    monkeypatch.setattr(n.requests, "post", lambda *a, **k: pytest.fail("no call"))
    assert n.send_telegram_message("hi") is False
    assert n.send_telegram_video("x.mp4") is False


def test_send_message_payload(configured, monkeypatch):
    seen = {}

    def post(url, **kw):
        seen["url"], seen["kw"] = url, kw
        return Resp()

    monkeypatch.setattr(n.requests, "post", post)
    assert n.send_telegram_message("y" * 6000) is True
    assert seen["url"].endswith("/botT/sendMessage")
    assert seen["kw"]["json"]["chat_id"] == "42"
    assert len(seen["kw"]["json"]["text"]) == 4096
    assert seen["kw"]["timeout"] == 30


def test_send_message_failure_returns_false(configured, monkeypatch):
    monkeypatch.setattr(n.requests, "post", lambda *a, **k: Resp(fail=True))
    assert n.send_telegram_message("hi") is False


def test_upload_report_escapes_and_formats(configured, monkeypatch):
    sent = []
    monkeypatch.setattr(n, "send_telegram_message", lambda m, **k: sent.append(m) or True)
    n.send_upload_report("a<b", "c&d", "<t>", status="Failed", error_msg="x" * 3000,
                         video_url="http://u?a=1&b=2")
    msg = sent[0]
    assert "a&lt;b" in msg and "c&amp;d" in msg and "&lt;t&gt;" in msg
    assert "❌" in msg and "a=1&amp;b=2" in msg
    assert len(msg) < 4096
    n.send_upload_report("a", "c", "t")
    assert "✅" in sent[1] and "Error" not in sent[1]


def test_send_video(configured, monkeypatch, tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"123")
    seen = {}

    def post(url, **kw):
        seen.update(url=url, data=kw["data"], timeout=kw["timeout"])
        return Resp()

    monkeypatch.setattr(n.requests, "post", post)
    assert n.send_telegram_video(str(f), caption="cap") is True
    assert seen["data"] == {"chat_id": "42", "caption": "cap"}
    assert n.send_telegram_video(str(tmp_path / "missing.mp4")) is False

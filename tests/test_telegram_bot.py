import asyncio
import importlib
import logging
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("telegram")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def bot(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("API_BASE_URL", "http://api.test")
    monkeypatch.delenv("API_TOKEN", raising=False)
    for name in ("src.config", "src.telegram_bot"):
        sys.modules.pop(name, None)
    mod = importlib.import_module("src.telegram_bot")
    yield mod
    for name in ("src.config", "src.telegram_bot"):
        sys.modules.pop(name, None)


def command_update(text, chat_id=42):
    return SimpleNamespace(
        update_id=1,
        effective_chat=SimpleNamespace(id=chat_id),
        callback_query=None,
        effective_message=SimpleNamespace(text=text),
    )


def test_describe_command_with_args(bot):
    desc = bot.describe_update(command_update("/run acc chan"))
    assert desc == "command /run acc chan from chat 42"


def test_describe_redacts_add_channel_json(bot):
    desc = bot.describe_update(command_update('/add_channel {"password": "s3cret"}'))
    assert "s3cret" not in desc
    assert "/add_channel" in desc


def test_describe_button_and_plain_text(bot):
    upd = SimpleNamespace(
        effective_chat=SimpleNamespace(id=7),
        callback_query=SimpleNamespace(data="run:a:b"),
    )
    assert bot.describe_update(upd) == "button 'run:a:b' from chat 7"
    assert "chars" in bot.describe_update(command_update("hello"))


def test_log_update_logs_at_info(bot, caplog):
    with caplog.at_level(logging.INFO, logger="telegram_bot"):
        asyncio.run(bot.log_update(command_update("/status"), None))
    assert any(
        r.levelno == logging.INFO and "/status" in r.getMessage()
        for r in caplog.records
    )


def test_application_logs_before_commands(bot):
    app = bot.build_application("123:abc")
    assert any(h.callback is bot.log_update for h in app.handlers[-1])
    commands = {c for h in app.handlers[0] for c in getattr(h, "commands", ())}
    assert {"start", "status", "run", "logs", "disk"} <= commands


def test_main_without_token_fails(bot, monkeypatch):
    monkeypatch.setattr(bot, "TOKEN", None)
    assert bot.main() == 1


def test_script_imports_without_pythonpath(tmp_path):
    """`python src/telegram_bot.py` must import without PYTHONPATH and never poll."""
    script = os.path.join(ROOT, "src", "telegram_bot.py")
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    # Emulate a script run (sys.path[0] = src/) with polling disabled for safety.
    code = (
        "import runpy, sys;"
        f"sys.path[0] = {os.path.dirname(script)!r}; sys.argv = [{script!r}];"
        "import telegram.ext as t;"
        "t.Application.run_polling = lambda *a, **k: print('POLLING', file=sys.stderr);"
        f"runpy.run_path({script!r}, run_name='__main__')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(tmp_path),
        env={**env, "TELEGRAM_BOT_TOKEN": "", "DB_TYPE": "mysql"},
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    assert "TELEGRAM_BOT_TOKEN not found" in proc.stderr, proc.stderr
    assert proc.returncode == 1
    assert "POLLING" not in proc.stderr


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self._text = text

    def json(self):
        if self._text is not None:
            raise ValueError("not json")
        return self._payload


class FakeApi:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.is_closed = False

    async def _call(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    async def get(self, url, **kw):
        return await self._call("GET", url, **kw)

    async def post(self, url, **kw):
        return await self._call("POST", url, **kw)

    async def delete(self, url, **kw):
        return await self._call("DELETE", url, **kw)


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.replies = []

    async def reply_html(self, text, **kw):
        self.replies.append(("html", text, kw))

    async def reply_text(self, text, **kw):
        self.replies.append(("text", text, kw))


def make_update(text="", chat_id=42):
    msg = FakeMessage(text)
    upd = SimpleNamespace(
        update_id=1,
        effective_chat=SimpleNamespace(id=chat_id),
        callback_query=None,
        effective_message=msg,
        message=msg,
    )
    return upd, msg


def use_api(bot, monkeypatch, response):
    fake = FakeApi(response)
    monkeypatch.setattr(bot, "_api", fake)
    return fake


def test_get_api_carries_token_and_base_url(bot, monkeypatch):
    monkeypatch.setattr(bot.Config, "API_TOKEN", "tok")
    client = bot.get_api()
    try:
        assert client.headers["X-API-Token"] == "tok"
        assert str(client.base_url).startswith("http://api.test")
    finally:
        asyncio.run(bot.close_api())
    assert bot._api is None


def test_run_command_posts_channel(bot, monkeypatch):
    fake = use_api(bot, monkeypatch, FakeResponse(200, {}))
    upd, msg = make_update("/run acc chan")
    asyncio.run(bot.run_command(upd, SimpleNamespace(args=["acc", "chan"])))
    assert fake.calls[0][:2] == ("POST", "/run/channel")
    assert fake.calls[0][2]["params"] == {"account_name": "acc", "channel_name": "chan"}
    assert "Started" in msg.replies[0][1]


def test_unauthorized_chat_is_ignored(bot, monkeypatch):
    fake = use_api(bot, monkeypatch, FakeResponse(200, {}))
    upd, msg = make_update("/status", chat_id=999)
    asyncio.run(bot.status_command(upd, SimpleNamespace(args=[])))
    assert fake.calls == []
    assert msg.replies == []


def test_api_down_reports_error(bot, monkeypatch):
    use_api(bot, monkeypatch, ConnectionError("refused"))
    upd, msg = make_update("/status")
    asyncio.run(bot.status_command(upd, SimpleNamespace(args=[])))
    assert "refused" in msg.replies[0][1]


def test_status_escapes_job_and_reports_http_errors(bot, monkeypatch):
    use_api(bot, monkeypatch, FakeResponse(200, {"status": "Running", "job": "<x>"}))
    upd, msg = make_update("/status")
    asyncio.run(bot.status_command(upd, SimpleNamespace(args=[])))
    assert "&lt;x&gt;" in msg.replies[0][1]

    use_api(bot, monkeypatch, FakeResponse(401, {"error": "Unauthorized"}))
    upd, msg = make_update("/status")
    asyncio.run(bot.status_command(upd, SimpleNamespace(args=[])))
    assert "Unauthorized" in msg.replies[0][1]


def test_run_command_non_json_error_body(bot, monkeypatch):
    use_api(bot, monkeypatch, FakeResponse(502, text="<html>Bad gateway</html>"))
    upd, msg = make_update("/run a b")
    asyncio.run(bot.run_command(upd, SimpleNamespace(args=["a", "b"])))
    assert "HTTP 502" in msg.replies[0][1]


def test_channels_escapes_names_and_skips_long_buttons(bot, monkeypatch):
    channels = [
        {"account_name": "a<b", "channel_name": "c"},
        {"account_name": "x" * 40, "channel_name": "y" * 40},
    ]
    use_api(bot, monkeypatch, FakeResponse(200, channels))
    upd, msg = make_update("/channels")
    asyncio.run(bot.channels_command(upd, SimpleNamespace(args=[])))
    _, first, first_kw = msg.replies[1]
    assert "a&lt;b" in first and "reply_markup" in first_kw
    _, second, second_kw = msg.replies[2]
    assert "too long" in second and "reply_markup" not in second_kw


def test_malformed_button_data_is_ignored(bot, monkeypatch):
    fake = use_api(bot, monkeypatch, FakeResponse(200, {}))
    answered = []

    async def answer():
        answered.append(True)

    query = SimpleNamespace(data="garbage", answer=answer)
    upd = SimpleNamespace(effective_chat=SimpleNamespace(id=42), callback_query=query)
    asyncio.run(bot.button_callback(upd, None))
    assert answered and fake.calls == []


def test_add_channel_rejects_non_object(bot, monkeypatch):
    fake = use_api(bot, monkeypatch, FakeResponse(201, {}))
    upd, msg = make_update("/add_channel [1]")
    asyncio.run(bot.add_channel_command(upd, SimpleNamespace(args=["[1]"])))
    assert fake.calls == [] and "JSON object" in msg.replies[0][1]


def test_disk_escapes_values(bot, monkeypatch):
    use_api(bot, monkeypatch, FakeResponse(200, {"<dir>": "1 MB"}))
    upd, msg = make_update("/disk")
    asyncio.run(bot.disk_command(upd, SimpleNamespace(args=[])))
    assert "&lt;dir&gt;" in msg.replies[0][1]

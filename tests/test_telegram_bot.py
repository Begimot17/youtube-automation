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
    desc = bot.describe_update(
        command_update('/add_channel {"password": "s3cret"}')
    )
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
        r.levelno == logging.INFO and "/status" in r.getMessage() for r in caplog.records
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
        text=True,
        timeout=60,
    )
    assert "TELEGRAM_BOT_TOKEN not found" in proc.stderr, proc.stderr
    assert proc.returncode == 1
    assert "POLLING" not in proc.stderr

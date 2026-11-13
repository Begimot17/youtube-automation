import pytest

from src.upload_engine import helpers
from src.upload_engine.helpers import (
    clamp_title,
    cookies_path_for,
    css_quote,
    parse_proxy,
    retry_step,
    xpath_literal,
)


def test_cookies_path_cannot_escape():
    assert cookies_path_for("Sugarfilip75") == "auth/Sugarfilip75.json"
    assert cookies_path_for("a@b.com") == "auth/a@b.com.json"
    p = cookies_path_for("../../etc/passwd")
    assert p.startswith("auth/") and p.count("/") == 1 and "\\" not in p
    assert cookies_path_for("..") == "auth/default.json"
    assert cookies_path_for("a" + chr(92) + "b/c") == "auth/a_b_c.json"
    assert cookies_path_for(None) == "auth/default.json"
    assert cookies_path_for("  ") == "auth/default.json"


def test_parse_proxy():
    assert parse_proxy("") is None
    assert parse_proxy(None) is None
    assert parse_proxy("1.2.3.4:8080") == {"server": "http://1.2.3.4:8080"}
    assert parse_proxy("socks5://u:p%40ss@h.example:1080") == {
        "server": "socks5://h.example:1080",
        "username": "u",
        "password": "p@ss",
    }
    assert parse_proxy("http://host") == {"server": "http://host"}
    assert parse_proxy("http://:80") is None


def test_css_quote_and_xpath_literal():
    assert css_quote("it's") == "it\'s"
    assert xpath_literal("plain") == "'plain'"
    assert xpath_literal("it's") == '"it\'s"'
    assert xpath_literal("a'b\"c") == "concat('a', \"'\", 'b\"c')"


def test_clamp_title():
    assert clamp_title("short #shorts") == "short #shorts"
    assert clamp_title("") == "New Video"
    assert clamp_title(None) == "New Video"
    assert clamp_title("  many   spaces ") == "many spaces"
    long = ("word " * 40).strip()
    out = clamp_title(long)
    assert len(out) <= 100 and out.endswith("word") and not out.endswith(" ")
    assert len(clamp_title("x" * 300)) == 100


def test_retry_step_succeeds_after_failures(monkeypatch):
    sleeps = []
    monkeypatch.setattr(helpers.time, "sleep", sleeps.append)
    calls = []

    @retry_step(max_attempts=3, base_delay=2.0, step_name="t")
    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("boom")
        return "ok"

    assert flaky() == "ok"
    assert sleeps == [2.0, 4.0]


def test_retry_step_raises_after_exhaustion(monkeypatch):
    monkeypatch.setattr(helpers.time, "sleep", lambda s: None)
    calls = []

    @retry_step(max_attempts=2)
    def bad():
        calls.append(1)
        raise ValueError("nope")

    with pytest.raises(ValueError):
        bad()
    assert len(calls) == 2

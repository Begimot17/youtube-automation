import importlib

import pytest

from src import config as config_module
from src.config import env_bool, env_int


@pytest.fixture
def reload_config(monkeypatch):
    # Never let a developer's real .env leak into the assertions.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)

    def _reload(**env):
        for k in ("TIKTOK_DOWNLOAD_COUNT", "PORT", "DEBUG", "GOOGLE_API_KEY",
                  "GEMINI_API_KEY", "GEMINI_MODEL_ID", "PEXELS_API_KEY"):
            monkeypatch.delenv(k, raising=False)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        return importlib.reload(config_module).Config

    yield _reload
    monkeypatch.undo()
    importlib.reload(config_module)


def test_env_int(monkeypatch):
    monkeypatch.setenv("X_N", "7")
    assert env_int("X_N", 1) == 7
    monkeypatch.setenv("X_N", " 9 ")
    assert env_int("X_N", 1) == 9
    monkeypatch.setenv("X_N", "abc")
    assert env_int("X_N", 1) == 1
    monkeypatch.setenv("X_N", "")
    assert env_int("X_N", 4) == 4
    monkeypatch.setenv("X_N", "0")
    assert env_int("X_N", 3, minimum=1) == 3
    monkeypatch.delenv("X_N")
    assert env_int("X_N", 5) == 5


def test_env_bool(monkeypatch):
    for v in ("true", "1", "T", "Yes", "on"):
        monkeypatch.setenv("X_B", v)
        assert env_bool("X_B") is True
    for v in ("false", "0", "no", "", "nonsense"):
        monkeypatch.setenv("X_B", v)
        assert env_bool("X_B") is False
    monkeypatch.delenv("X_B")
    assert env_bool("X_B", True) is True


def test_tiktok_count_is_int(reload_config):
    cfg = reload_config(TIKTOK_DOWNLOAD_COUNT="3")
    assert cfg.TIKTOK_DOWNLOAD_COUNT == 3
    assert isinstance(reload_config().TIKTOK_DOWNLOAD_COUNT, int)


def test_bad_port_falls_back(reload_config):
    assert reload_config(PORT="oops").PORT == 5000
    assert reload_config(PORT="8080").PORT == 8080


def test_api_key_fallback_and_validate(reload_config):
    cfg = reload_config(GEMINI_API_KEY="g", PEXELS_API_KEY="p")
    assert cfg.GOOGLE_API_KEY == "g"
    assert cfg.validate() is True
    cfg = reload_config()
    assert cfg.validate() is False


def test_default_model(reload_config):
    assert reload_config().GEMINI_MODEL_ID == "gemini-2.5-flash-lite"
    assert reload_config(GEMINI_MODEL_ID="m").GEMINI_MODEL_ID == "m"

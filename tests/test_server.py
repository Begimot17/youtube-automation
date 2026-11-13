import importlib
import sys
import types

import pytest


@pytest.fixture
def server(tmp_path, monkeypatch):
    """Imports src.server against a temp sqlite DB with heavy deps stubbed out."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 't.db').as_posix()}")
    monkeypatch.delenv("API_TOKEN", raising=False)

    stub_main = types.ModuleType("main")
    stub_main.run_for_channel = lambda *a, **k: None
    stub_main.run_full_cycle = lambda *a, **k: None
    stub_factory = types.ModuleType("src.factory")
    stub_factory.create_content = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "main", stub_main)
    try:
        import alembic.command  # noqa: F401
    except ImportError:  # alembic is only needed for run_migrations()
        pkg = types.ModuleType("alembic")
        pkg.command = types.ModuleType("alembic.command")
        pkg.config = types.ModuleType("alembic.config")
        pkg.config.Config = object
        monkeypatch.setitem(sys.modules, "alembic", pkg)
        monkeypatch.setitem(sys.modules, "alembic.command", pkg.command)
        monkeypatch.setitem(sys.modules, "alembic.config", pkg.config)
    monkeypatch.setitem(sys.modules, "src.factory", stub_factory)
    for name in ("src.config", "src.utils.db", "src.server"):
        sys.modules.pop(name, None)

    mod = importlib.import_module("src.server")
    from src.utils import db

    db.Base.metadata.create_all(bind=db.engine)
    mod.app.config["TESTING"] = True
    yield mod
    db.engine.dispose()
    for name in ("src.config", "src.utils.db", "src.server"):
        sys.modules.pop(name, None)


def test_health_is_open_even_with_token(server, monkeypatch):
    monkeypatch.setattr(server.Config, "API_TOKEN", "tok")
    c = server.app.test_client()
    assert c.get("/health").status_code == 200
    assert c.get("/status").status_code == 401
    assert c.get("/status", headers={"X-API-Token": "tok"}).status_code == 200
    assert c.get("/status", headers={"Authorization": "Bearer tok"}).status_code == 200
    assert c.get("/status", headers={"X-API-Token": "bad"}).status_code == 401


def test_open_without_token(server):
    assert server.app.test_client().get("/status").status_code == 200


def test_channel_crud_roundtrip(server):
    c = server.app.test_client()
    r = c.post("/channel", json={"account_name": "a", "channel_name": "b",
                                 "password": "secret"})
    assert r.status_code == 201
    assert c.post("/channel", json={"account_name": "a", "channel_name": "b"}).status_code == 409
    got = c.get("/channel?account_name=a&channel_name=b").get_json()
    assert got["password"] == "******"
    assert got["schedule"] == ["08:00-20:00"]
    assert c.get("/channels").get_json() == [{"account_name": "a", "channel_name": "b"}]
    assert c.delete("/channel?account_name=a&channel_name=b").status_code == 200
    assert c.get("/channel?account_name=a&channel_name=b").status_code == 404


def test_bad_json_bodies_are_400(server):
    c = server.app.test_client()
    assert c.post("/channel", data="not json", content_type="application/json").status_code == 400
    assert c.post("/channel", data="x").status_code == 400
    assert c.post("/notify", data="x").status_code == 400
    assert c.post("/render/custom", data="x").status_code == 400
    assert c.post("/config", data="x").status_code == 400


def test_config_post_sets_and_validates_schedule(server):
    c = server.app.test_client()
    r = c.post("/config", json=[{"account_name": "a", "channel_name": "b",
                                 "schedule": ["22:00-02:00"]}])
    assert r.status_code == 200
    got = c.get("/config").get_json()
    assert got[0]["schedule"] == ["22:00-02:00"]
    r = c.post("/config", json=[{"account_name": "a", "channel_name": "b",
                                 "schedule": ["nonsense"]}])
    assert r.status_code == 400
    assert c.get("/config").get_json()[0]["schedule"] == ["22:00-02:00"]


def test_logs_tail(server, tmp_path):
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "app.log").write_text(
        "".join(f"l{i}\n" for i in range(250)), encoding="utf-8"
    )
    lines = server.app.test_client().get("/logs").get_json()
    assert len(lines) == 100 and lines[-1] == "l249\n" and lines[0] == "l150\n"

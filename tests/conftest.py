import importlib
import os
import sys
import types

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Keep imports of src.config free of side effects on the real data directory.
os.environ.setdefault("DB_TYPE", "mysql")


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



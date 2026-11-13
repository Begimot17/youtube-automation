import json

import pytest

from src.utils.channel_io import fields_from_json, is_real_password


def test_is_real_password():
    assert is_real_password("hunter2")
    assert is_real_password("a*b")
    for v in (None, "", "   ", "***", "******"):
        assert not is_real_password(v)


def test_fields_from_json_only_present_keys():
    f = fields_from_json({"channel_name": "c", "quality": "hard", "password": "***"})
    assert f == {"quality": "hard"}


def test_fields_from_json_schedule_validated():
    assert fields_from_json({"schedule": ["8:00-9:00"]}) == {"schedule": ["08:00-09:00"]}
    with pytest.raises(ValueError):
        fields_from_json({"schedule": ["nope"]})


@pytest.fixture
def migrate_mod(server):
    import importlib

    import src.scripts.migrate_to_db as m

    importlib.reload(m)
    return m


def test_resync_does_not_clobber_password_or_schedule(migrate_mod):
    from src.utils.db import Channel, SessionLocal

    db = SessionLocal()
    migrate_mod.sync_channel(db, {"channel_name": "c", "account_name": "a",
                                  "password": "real", "schedule": ["22:00-02:00"]})
    db.commit()
    # Same entry as shipped in config/channels.json: masked password, no schedule.
    migrate_mod.sync_channel(db, {"channel_name": "c", "account_name": "a",
                                  "password": "***", "quality": "hard"})
    db.commit()
    ch = db.query(Channel).one()
    assert ch.password == "real"
    assert ch.schedule == ["22:00-02:00"]
    assert ch.quality == "hard"
    db.close()


def test_create_applies_defaults_and_account_fallback(migrate_mod):
    from src.utils.db import Channel, SessionLocal

    db = SessionLocal()
    migrate_mod.sync_channel(db, {"channel_name": "solo", "tiktok_sources": ["u"]})
    db.commit()
    ch = db.query(Channel).one()
    assert ch.account_name == "solo"
    assert ch.mode == "tiktok" and ch.upload_frequency_per_day == 1
    assert ch.schedule == ["08:00-20:00"] and ch.tiktok_sources == ["u"]
    db.close()


def test_migrate_skips_bad_entries_and_keeps_good(migrate_mod, tmp_path, monkeypatch):
    from src.utils.db import Channel, SessionLocal

    cfg = tmp_path / "channels.json"
    cfg.write_text(json.dumps([
        {"account_name": "x"},
        {"channel_name": "bad", "schedule": ["zzz"]},
        {"channel_name": "good", "account_name": "g"},
    ]), encoding="utf-8")
    monkeypatch.setattr(migrate_mod.Config, "CHANNELS_CONFIG_PATH", str(cfg))
    monkeypatch.setattr(migrate_mod.Config, "UPLOAD_HISTORY_PATH", str(tmp_path / "none.json"))
    migrate_mod.migrate()
    db = SessionLocal()
    assert [c.channel_name for c in db.query(Channel).all()] == ["good"]
    db.close()

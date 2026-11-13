from types import SimpleNamespace

import pytest

from src.utils.channel_io import apply_channel_update, serialize_channel


def make(**kw):
    base = dict(
        channel_name="c", account_name="a", mode="tiktok", gmail="g@x", password="pw",
        watch_folder="w", proxy="", upload_frequency_per_day=1, min_delay_seconds=60,
        quality="easy", lang="ru", voice=None, tiktok_sources=["u"], genai_topics=[],
        schedule='["08:00-20:00"]',
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_serialize_hides_password_and_normalizes_schedule():
    out = serialize_channel(make())
    assert out["password"] == "******"
    assert "pw" not in str(out)
    assert out["schedule"] == ["08:00-20:00"]
    assert out["tiktok_sources"] == ["u"]


def test_serialize_keeps_corrupt_schedule_visible():
    assert serialize_channel(make(schedule=["bad"]))["schedule"] == ["bad"]


def test_apply_update_partial():
    ch = make()
    apply_channel_update(ch, {"quality": "hard", "password": "new", "ignored": 1})
    assert (ch.quality, ch.password, ch.lang) == ("hard", "new", "ru")
    assert not hasattr(ch, "ignored")


def test_apply_update_schedule_validated_before_mutation():
    ch = make()
    with pytest.raises(ValueError):
        apply_channel_update(ch, {"quality": "hard", "schedule": ["zzz"]})
    assert ch.quality == "easy"
    apply_channel_update(ch, {"schedule": "22:00-02:00"})
    assert ch.schedule == ["22:00-02:00"]

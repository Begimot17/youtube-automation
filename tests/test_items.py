import random

from src.utils.items import pick_topic, tiktok_title, topic_item_id, upload_allowed


def test_topic_item_id_matches_legacy_format():
    assert topic_item_id("genai", "Hello World", "ru") == "genai_hello_world_ru"
    # persisted format: spaces map 1:1 to underscores
    assert topic_item_id("gen_v2", "A  b", "en") == "gen_v2_a__b_en"


def test_tiktok_title():
    assert tiktok_title("Funny cat") == "Funny cat #shorts #tiktok"
    assert tiktok_title(None) == "#shorts #tiktok"
    assert tiktok_title("") == "#shorts #tiktok"
    out = tiktok_title("x" * 200)
    assert out == "x" * 70 + " #shorts #tiktok"
    assert len(out) <= 100


def test_upload_allowed():
    assert upload_allowed(0, 2, 0, 1000, 3600) == (True, "")
    assert upload_allowed(0, 2, None, 1000, 3600) == (True, "")
    ok, why = upload_allowed(2, 2, 0, 1000, 3600)
    assert not ok and "2/2" in why
    ok, why = upload_allowed(1, 2, 900, 1000, 3600)
    assert not ok and "3500s" in why
    assert upload_allowed(1, 2, 0, 1000, 3600)[0]
    assert upload_allowed(1, 2, 100, 100 + 3600, 3600)[0]
    # falsy config values fall back to defaults
    assert not upload_allowed(1, None, 0, 1000, None)[0]
    assert not upload_allowed(0, 0, 500, 1000, 0)[0]


def test_pick_topic_skips_processed():
    done = {"genai_b_ru"}
    t, i = pick_topic(["a", "b"], lambda x: x in done, "genai", "ru", random.Random(1))
    assert (t, i) == ("a", "genai_a_ru")
    done.add("genai_a_ru")
    assert pick_topic(["a", "b"], lambda x: x in done, "genai", "ru") == (None, None)
    assert pick_topic([], lambda x: False, "genai", "ru") == (None, None)

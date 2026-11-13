import json

import pytest

from src.gen.parsing import loads_llm_json, normalize_script, normalize_words


def test_loads_plain_and_fenced():
    assert loads_llm_json('{"a": 1}') == {"a": 1}
    assert loads_llm_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert loads_llm_json('```\n[1, 2]\n```') == [1, 2]


def test_loads_invalid():
    with pytest.raises(ValueError):
        loads_llm_json(None)
    with pytest.raises(json.JSONDecodeError):
        loads_llm_json("not json")


def test_normalize_script_happy_path():
    out = normalize_script(
        {"script": " Hi there ", "scenes": [{"text": "Hi", "keywords": [" a ", "b"]}]}
    )
    assert out == {"script": "Hi there", "scenes": [{"text": "Hi", "keywords": ["a", "b"]}]}


@pytest.mark.parametrize(
    "bad", [None, "x", 5, {}, {"script": ""}, {"script": "  "}, {"script": 3}, []]
)
def test_normalize_script_rejects(bad):
    assert normalize_script(bad) is None


def test_normalize_script_unwraps_single_item_list():
    assert normalize_script([{"script": "x"}]) == {"script": "x", "scenes": []}


def test_normalize_script_cleans_scenes():
    out = normalize_script(
        {
            "script": "s",
            "scenes": [
                "junk",
                {"text": None, "keywords": "ocean"},
                {"keywords": [1, "", "  ", "ok"]},
                {"text": "t", "keywords": None},
            ],
        }
    )
    assert out["scenes"] == [
        {"text": "", "keywords": ["ocean"]},
        {"text": "", "keywords": ["ok"]},
        {"text": "t", "keywords": []},
    ]


def test_normalize_script_scenes_not_list():
    assert normalize_script({"script": "s", "scenes": "x"})["scenes"] == []


def test_normalize_words():
    raw = [
        {"word": "b", "start": "1.5", "end": 2},
        {"word": "a", "start": 0.1, "end": 0.5},
        {"word": "bad", "start": None, "end": 1},
        {"word": "", "start": 1, "end": 2},
        {"word": "neg", "start": -1, "end": 2},
        {"word": "rev", "start": 3, "end": 2.5},
        "junk",
    ]
    assert normalize_words(raw) == [
        {"word": "a", "start": 0.1, "end": 0.5},
        {"word": "b", "start": 1.5, "end": 2.0},
        {"word": "rev", "start": 3.0, "end": 3.0},
    ]


def test_normalize_words_wrapped_and_garbage():
    assert normalize_words({"words": [{"word": "x", "start": 0, "end": 1}]}) == [
        {"word": "x", "start": 0.0, "end": 1.0}
    ]
    assert normalize_words("nope") == []
    assert normalize_words(None) == []

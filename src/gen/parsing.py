"""Pure parsing/validation of LLM output (no network or SDK imports)."""

import json
import re

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


def loads_llm_json(text):
    """json.loads that tolerates a surrounding ```json fence."""
    if text is None:
        raise ValueError("empty response")
    text = text.strip()
    m = _FENCE_RE.match(text)
    if m:
        text = m.group(1)
    return json.loads(text)


def normalize_script(data, topic=""):
    """
    Validates/normalizes a generated script structure.
    Returns {"script": str, "scenes": [{"text": str, "keywords": [str, ...]}]}
    or None when no usable script text is present.
    """
    if isinstance(data, list) and len(data) == 1:
        data = data[0]
    if not isinstance(data, dict):
        return None

    script = data.get("script")
    if not isinstance(script, str) or not script.strip():
        return None

    scenes = []
    raw_scenes = data.get("scenes")
    for raw in raw_scenes if isinstance(raw_scenes, list) else []:
        if not isinstance(raw, dict):
            continue
        kw = raw.get("keywords")
        if isinstance(kw, str):
            kw = [kw]
        if not isinstance(kw, list):
            kw = []
        kw = [k.strip() for k in kw if isinstance(k, str) and k.strip()]
        text = raw.get("text")
        scenes.append(
            {"text": text.strip() if isinstance(text, str) else "", "keywords": kw}
        )
    return {"script": script.strip(), "scenes": scenes}


def normalize_words(raw):
    """
    Validates word-level timestamps: [{"word", "start", "end"}].
    Drops malformed items, coerces numbers, fixes end < start and sorts by start.
    """
    if isinstance(raw, dict):
        raw = raw.get("words", [])
    if not isinstance(raw, list):
        return []
    words = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        word = item.get("word")
        try:
            start = float(item.get("start"))
            end = float(item.get("end"))
        except (TypeError, ValueError):
            continue
        if not isinstance(word, str) or not word.strip() or start < 0:
            continue
        if end < start:
            end = start
        words.append({"word": word.strip(), "start": start, "end": end})
    words.sort(key=lambda w: w["start"])
    return words

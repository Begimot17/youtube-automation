from src.gen.scenes import collect_visuals


def make_fetch(fail=()):
    calls = []

    def fetch(query, out, used):
        calls.append((query, out, set(used)))
        if query in fail:
            return None, None
        return out, f"url:{query}"

    fetch.calls = calls
    return fetch


def test_one_visual_per_scene_and_unique_tracking():
    f = make_fetch()
    scenes = [{"keywords": ["a", "b"]}, {"keywords": ["c"]}]
    paths = collect_visuals(scenes, "topic", "d", f)
    assert [c[0] for c in f.calls] == ["a", "c"]
    assert len(paths) == 2
    assert f.calls[1][2] == {"url:a"}


def test_falls_back_to_second_keyword_on_failure():
    f = make_fetch(fail={"a"})
    paths = collect_visuals([{"keywords": ["a", "b", "c"]}], "t", "d", f)
    assert [c[0] for c in f.calls] == ["a", "b"]
    assert len(paths) == 1 and paths[0].endswith("scene_0_v1.mp4")


def test_empty_keywords_use_topic():
    f = make_fetch()
    collect_visuals([{"keywords": []}, {}, {"keywords": ["", None]}], "T", "d", f)
    assert [c[0] for c in f.calls] == ["T", "T", "T"]


def test_all_fail_and_no_scenes():
    assert collect_visuals([{"keywords": ["a"]}], "t", "d", make_fetch(fail={"a"})) == []
    assert collect_visuals(None, "t", "d", make_fetch()) == []


def test_per_scene_two():
    f = make_fetch()
    paths = collect_visuals([{"keywords": ["a", "b", "c"]}], "t", "d", f, per_scene=2)
    assert len(paths) == 2 and [c[0] for c in f.calls] == ["a", "b"]

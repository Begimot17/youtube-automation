import numpy as np

from src.rendering import text_image as ti


def test_output_is_cropped_not_full_frame():
    arr = ti.render_text_image("Hello", max_width=1080)
    assert arr.ndim == 3 and arr.shape[2] == 4
    assert arr.shape[0] < 400 and arr.shape[1] < 1080
    assert arr.nbytes < 1080 * 1920 * 4 / 4


def test_has_visible_pixels_and_transparent_background():
    arr = ti.render_text_image("Hi", max_width=1080)
    alpha = arr[:, :, 3]
    assert alpha.max() == 255
    assert alpha[0, 0] == 0


def test_wider_text_is_scaled_down_to_max_width():
    arr = ti.render_text_image("W" * 40, max_width=300)
    assert arr.shape[1] == 300


def test_longer_text_is_wider():
    a = ti.render_text_image("a", max_width=5000)
    b = ti.render_text_image("aaaaaa", max_width=5000)
    assert b.shape[1] > a.shape[1]


def test_font_fallback_and_cache(tmp_path):
    f1 = ti.load_font(20, candidates=[str(tmp_path / "missing.ttf")])
    f2 = ti.load_font(20, candidates=[str(tmp_path / "missing.ttf")])
    assert f1 is f2

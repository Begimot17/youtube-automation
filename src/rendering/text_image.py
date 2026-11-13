"""Tight-bounding-box subtitle rendering with PIL (no moviepy import)."""

import logging
import os

import numpy as np
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

logger = logging.getLogger(__name__)

_FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")
FONT_CANDIDATES = [
    os.path.join(_FONT_DIR, "LiberationSans-Bold.ttf"),
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]

_font_cache = {}


def load_font(size, candidates=None):
    """Loads the first available TrueType font (cached), else PIL's default."""
    key = (size, tuple(candidates) if candidates else None)
    if key in _font_cache:
        return _font_cache[key]
    font = None
    for p in candidates or FONT_CANDIDATES:
        try:
            if os.path.exists(p):
                font = PIL.ImageFont.truetype(p, size)
                break
        except Exception:
            continue
    if font is None:
        logger.warning("No suitable font found. Loading default.")
        font = PIL.ImageFont.load_default()
    _font_cache[key] = font
    return font


def render_text_image(text, max_width, color="yellow", font_size=120, stroke=3, font=None):
    """
    Renders `text` with a black outline into an RGBA array cropped to the text
    bounds (+ stroke padding). A full-frame canvas per word cost ~8 MB each at
    1080x1920; this is typically a few hundred KB.
    """
    font = font or load_font(font_size)
    probe = PIL.ImageDraw.Draw(PIL.Image.new("RGBA", (1, 1)))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    w, h = right - left, bottom - top
    pad = stroke + 1
    img = PIL.Image.new("RGBA", (max(1, w + 2 * pad), max(1, h + 2 * pad)), (0, 0, 0, 0))
    draw = PIL.ImageDraw.Draw(img)
    x, y = pad - left, pad - top
    draw.text((x, y), text, font=font, fill=color, stroke_width=stroke, stroke_fill="black")
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, max(1, int(img.height * ratio))))
    return np.array(img)

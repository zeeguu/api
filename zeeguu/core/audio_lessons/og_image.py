"""
Open Graph preview card for a shared audio lesson.

Social scrapers (WhatsApp, iMessage, Slack, Facebook, ...) don't run JS, so a
shared `/shared-lesson/<uuid>` link otherwise falls back to the generic site
preview. This renders a 1200x630 PNG card from a lesson's public view dict
(the same data returned by DailyLessonGenerator.get_shared_lesson_view) so the
preview shows the actual lesson: title, language, duration, CEFR level, words.

Pure function of the view dict + brand assets — no DB access — so it's trivial
to unit-test and to render samples. Cards are immutable per lesson, so callers
cache the PNG on disk (see ensure_cached_card).
"""

import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

# 1.91:1 — the ratio every major scraper crops to.
WIDTH, HEIGHT = 1200, 630
MARGIN = 70

_ASSETS = os.path.join(os.path.dirname(__file__), "assets")
_FONTS = os.path.join(_ASSETS, "fonts")
_LOGO_PATH = os.path.join(_ASSETS, "zeeguu-logo.png")

# Warm Zeeguu palette (mirrors web/src/components/colors.js).
BG_TOP = (255, 248, 230)      # cream
BG_BOTTOM = (255, 230, 188)   # light amber
INK = (74, 50, 8)             # dark brown — primary text
INK_SOFT = (140, 110, 60)     # muted brown — secondary text
ORANGE = (255, 168, 40)       # zeeguuOrange-ish, brand accent
ORANGE_DEEP = (196, 120, 24)  # darker orange for the wordmark
CHIP_BORDER = (224, 190, 130)
WHITE = (255, 255, 255)

_LANGUAGE_NAMES = {
    "da": "Danish", "de": "German", "es": "Spanish", "fr": "French",
    "nl": "Dutch", "en": "English", "it": "Italian", "pt": "Portuguese",
    "ro": "Romanian", "sv": "Swedish", "no": "Norwegian", "pl": "Polish",
    "ru": "Russian", "hu": "Hungarian",
}


def language_name(code):
    if not code:
        return None
    return _LANGUAGE_NAMES.get(code.lower(), code.upper())


@lru_cache(maxsize=None)
def _font(weight, size):
    return ImageFont.truetype(os.path.join(_FONTS, f"Montserrat-{weight}.ttf"), size)


def _text_w(draw, text, font):
    return draw.textlength(text, font=font)


def _wrap(draw, text, font, max_width, max_lines):
    """Greedy word wrap; the last line gets an ellipsis if text is truncated."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if _text_w(draw, candidate, font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) == max_lines:
                break
    if len(lines) < max_lines and current:
        lines.append(current)

    truncated = len(lines) == max_lines and (
        current != lines[-1] or len(" ".join(words)) > len(" ".join(lines))
    )
    if truncated:
        last = lines[-1]
        while last and _text_w(draw, last + "…", font) > max_width:
            last = last[:-1].rstrip()
        lines[-1] = last + "…"
    return lines


def _rounded(draw, box, radius, **kwargs):
    draw.rounded_rectangle(box, radius=radius, **kwargs)


def _draw_chip(draw, x, y, text, font, *, filled):
    """Draws a pill at (x, y); returns the x just past its right edge."""
    pad_x, pad_y = 22, 12
    tw = _text_w(draw, text, font)
    ascent, descent = font.getmetrics()
    th = ascent + descent
    box = (x, y, x + tw + 2 * pad_x, y + th + 2 * pad_y)
    if filled:
        _rounded(draw, box, radius=(th + 2 * pad_y) // 2, fill=ORANGE)
        draw.text((x + pad_x, y + pad_y), text, font=font, fill=WHITE)
    else:
        _rounded(draw, box, radius=(th + 2 * pad_y) // 2,
                 fill=WHITE, outline=CHIP_BORDER, width=2)
        draw.text((x + pad_x, y + pad_y), text, font=font, fill=INK_SOFT)
    return box[2]


def _play_chip(draw, x, y, text, font):
    """A duration chip with a little play triangle in front of the text."""
    pad_x, pad_y, gap = 22, 12, 14
    tri = 22
    tw = _text_w(draw, text, font)
    ascent, descent = font.getmetrics()
    th = ascent + descent
    box = (x, y, x + pad_x + tri + gap + tw + pad_x, y + th + 2 * pad_y)
    _rounded(draw, box, radius=(th + 2 * pad_y) // 2,
             fill=WHITE, outline=CHIP_BORDER, width=2)
    cy = y + (th + 2 * pad_y) / 2
    tx = x + pad_x
    draw.polygon(
        [(tx, cy - tri / 2), (tx, cy + tri / 2), (tx + tri * 0.9, cy)],
        fill=ORANGE_DEEP,
    )
    draw.text((tx + tri + gap, y + pad_y), text, font=font, fill=INK_SOFT)
    return box[2]


def _format_duration(seconds):
    if not seconds:
        return None
    minutes = max(1, round(seconds / 60))
    return f"{minutes} min"


def _lesson_type_label(lesson_type):
    return {
        "three_words_lesson": "Vocabulary",
        "topic": "Conversation",
        "situation": "Conversation",
    }.get(lesson_type)


def render_card(view):
    """Render the OG card for a lesson view dict and return a PIL Image."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_TOP)
    # Vertical cream→amber gradient.
    top, bottom = BG_TOP, BG_BOTTOM
    for y in range(HEIGHT):
        t = y / HEIGHT
        img.paste(
            tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)),
            (0, y, WIDTH, y + 1),
        )
    draw = ImageDraw.Draw(img)

    # Left brand accent bar.
    draw.rectangle((0, 0, 12, HEIGHT), fill=ORANGE)

    # --- Header: logo + wordmark (left), language pill (right) ---
    logo_size = 92
    try:
        logo = Image.open(_LOGO_PATH).convert("RGBA").resize((logo_size, logo_size))
        img.paste(logo, (MARGIN, MARGIN), logo)
    except OSError:
        logo = None
    wordmark_font = _font("ExtraBold", 44)
    wm_x = MARGIN + logo_size + 24
    wm_y = MARGIN + (logo_size - sum(wordmark_font.getmetrics())) // 2
    draw.text((wm_x, wm_y), "Zeeguu", font=wordmark_font, fill=ORANGE_DEEP)

    language = language_name(view.get("language_code"))
    if language:
        lang_font = _font("Bold", 32)
        lw = _text_w(draw, language, lang_font)
        _draw_chip(draw, WIDTH - MARGIN - lw - 44, MARGIN + 20, language,
                   lang_font, filled=True)

    # --- Title (vertically anchored in the middle band) ---
    title = (view.get("title") or "Audio lesson").strip()
    title_font = _font("Bold", 62)
    title_lines = _wrap(draw, title, title_font, WIDTH - 2 * MARGIN, max_lines=2)
    line_h = sum(title_font.getmetrics()) + 12
    title_y = MARGIN + logo_size + 60
    for i, line in enumerate(title_lines):
        draw.text((MARGIN, title_y + i * line_h), line, font=title_font, fill=INK)

    # --- Meta chips: duration · CEFR · type ---
    chips_y = title_y + len(title_lines) * line_h + 36
    chip_font = _font("SemiBold", 30)
    cursor = MARGIN
    duration = _format_duration(view.get("duration_seconds"))
    if duration:
        cursor = _play_chip(draw, cursor, chips_y, duration, chip_font) + 16
    cefr = view.get("cefr_level")
    if cefr:
        cursor = _draw_chip(draw, cursor, chips_y, cefr, chip_font, filled=True) + 16
    type_label = _lesson_type_label(view.get("lesson_type"))
    if type_label:
        cursor = _draw_chip(draw, cursor, chips_y, type_label, chip_font, filled=False)

    # --- Footer: the words being learned, else a tagline ---
    words = [w.get("origin") for w in (view.get("words") or []) if w.get("origin")]
    footer_font = _font("SemiBold", 30)
    if words:
        footer = "  ·  ".join(words[:5])
        footer = _wrap(draw, footer, footer_font, WIDTH - 2 * MARGIN, max_lines=1)[0]
    else:
        footer = "Listen, and pick up the words"
    draw.text((MARGIN, HEIGHT - MARGIN - sum(footer_font.getmetrics())),
              footer, font=footer_font, fill=INK_SOFT)

    # Bottom-right domain.
    dom_font = _font("Bold", 28)
    dom = "zeeguu.org"
    draw.text((WIDTH - MARGIN - _text_w(draw, dom, dom_font),
               HEIGHT - MARGIN - sum(dom_font.getmetrics())),
              dom, font=dom_font, fill=ORANGE_DEEP)

    return img


def card_png_bytes(view):
    from io import BytesIO

    buffer = BytesIO()
    render_card(view).save(buffer, format="PNG")
    return buffer.getvalue()


def cached_card_path(data_folder, lesson_id):
    return os.path.join(data_folder, "og-images", "shared-lessons", f"{lesson_id}.png")


def ensure_cached_card(view, data_folder):
    """Render (once) and cache the card PNG for this lesson; return its path.

    Lessons are immutable, so an existing file is reused. Returns None if the
    view has no lesson_id to key the cache on.
    """
    lesson_id = view.get("lesson_id")
    if not lesson_id:
        return None
    path = cached_card_path(data_folder, lesson_id)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        render_card(view).save(path, format="PNG")
    return path

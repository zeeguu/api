"""
Open Graph preview card for a shared audio lesson.

Social scrapers (WhatsApp, iMessage, Slack, Facebook, ...) don't run JS, so a
shared `/shared-lesson/<uuid>` link otherwise falls back to the generic site
preview. This renders a 1200x630 PNG card from a lesson's public view dict.

Design: the card is read at thumbnail size, so it carries only what survives
shrinking — the brand, the title as hero, a "<Language> Audio Lesson" pill, and
a play + soundform "listen" cue. Per-lesson metadata (duration, level, type)
lives in the og:description text instead, which stays legible at any size.

Pure function of the view dict + brand assets — no DB access — so it's trivial
to unit-test and render samples. Cards are immutable per lesson, so callers
cache the PNG on disk (see ensure_cached_card).
"""

import math
import os
import random
from functools import lru_cache

import zeeguu
from PIL import Image, ImageDraw, ImageFont

# 1.91:1 — the ratio every major scraper crops to.
WIDTH, HEIGHT = 1200, 630
MARGIN = 70

_ASSETS = os.path.join(os.path.dirname(zeeguu.__file__), "assets")
_FONTS = os.path.join(_ASSETS, "fonts")
_LOGO_PATH = os.path.join(_ASSETS, "images", "zeeguu-logo.png")

# Warm Zeeguu palette (mirrors web/src/components/colors.js).
BG_TOP = (255, 248, 230)      # cream
BG_BOTTOM = (255, 228, 186)   # light amber
INK = (74, 50, 8)             # dark brown — title
ORANGE = (255, 168, 40)       # brand accent / soundform
ORANGE_DEEP = (196, 120, 24)  # wordmark / play button
WHITE = (255, 255, 255)


@lru_cache(maxsize=None)
def _font(weight, size):
    return ImageFont.truetype(os.path.join(_FONTS, f"Montserrat-{weight}.ttf"), size)


def clean_lesson_title(title):
    """Drop the "Topic: " / "Situation: " prefix that display_title() prepends —
    it's clutter on a share card / preview title."""
    if not title:
        return title
    for prefix in ("Topic: ", "Situation: "):
        if title.startswith(prefix):
            return title[len(prefix):]
    return title


def _wrap(draw, text, font, max_width):
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_title(draw, text, max_width, max_height, max_lines=3):
    """Largest font (76→46) where the title fits in <=max_lines and <=max_height;
    falls back to the smallest size with an ellipsis if it still overflows."""
    for size in range(76, 45, -3):
        font = _font("Bold", size)
        lines = _wrap(draw, text, font, max_width)
        line_h = sum(font.getmetrics()) + 8
        if len(lines) <= max_lines and len(lines) * line_h <= max_height:
            return font, lines, line_h
    font = _font("Bold", 46)
    lines = _wrap(draw, text, font, max_width)
    line_h = sum(font.getmetrics()) + 8
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > max_width:
            last = last[:-1].rstrip()
        lines[-1] = last + "…"
    return font, lines, line_h


def _waveform(draw, x, y, width, height, color, bars=80, seed=5):
    """A fixed (deterministic) soundform — a row of rounded bars — spanning width."""
    rng = random.Random(seed)
    bar_w = width / (bars * 1.9)
    gap = bar_w * 0.9
    cx = x
    for i in range(bars):
        bh = height * (0.22 + 0.78 * abs(
            0.6 * math.sin(i * 0.55) + 0.5 * math.sin(i * 0.21) + 0.3 * rng.random()))
        bh = max(bar_w, min(height, bh))
        draw.rounded_rectangle(
            (cx, y + (height - bh) / 2, cx + bar_w, y + (height + bh) / 2),
            radius=bar_w / 2, fill=color)
        cx += bar_w + gap


def _play(draw, cx, cy, r, fill):
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)
    s = r * 0.5
    draw.polygon(
        [(cx - s * 0.45, cy - s), (cx - s * 0.45, cy + s), (cx + s * 0.85, cy)],
        fill=WHITE)


def _gradient_bg():
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_TOP)
    for y in range(HEIGHT):
        t = y / HEIGHT
        img.paste(
            tuple(round(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)),
            (0, y, WIDTH, y + 1))
    return img


def render_card(view):
    """Render the OG card for a lesson view dict and return a PIL Image."""
    img = _gradient_bg()
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 12, HEIGHT), fill=ORANGE)  # left brand accent

    # --- Header: logo + wordmark (left), "<Language> Audio Lesson" pill (right) ---
    logo_size = 78
    try:
        logo = Image.open(_LOGO_PATH).convert("RGBA").resize((logo_size, logo_size))
        img.paste(logo, (MARGIN, MARGIN), logo)
    except OSError:
        pass
    wordmark = _font("ExtraBold", 38)
    draw.text(
        (MARGIN + logo_size + 20, MARGIN + (logo_size - sum(wordmark.getmetrics())) // 2),
        "Zeeguu", font=wordmark, fill=ORANGE_DEEP)

    language = view.get("language_name")
    # The play button + soundform already say "audio", so the pill needn't repeat it.
    label = f"{language} Lesson" if language else "Lesson"
    pill_font = _font("Bold", 42)
    lw = draw.textlength(label, font=pill_font)
    asc, desc = pill_font.getmetrics()
    pill_top = MARGIN + 4
    draw.rounded_rectangle(
        (WIDTH - MARGIN - lw - 60, pill_top, WIDTH - MARGIN, pill_top + asc + desc + 30),
        radius=52, fill=ORANGE)
    draw.text((WIDTH - MARGIN - lw - 30, pill_top + 15), label, font=pill_font, fill=WHITE)

    # --- Title (hero): auto-fit, vertically centred between header and audio band ---
    title = clean_lesson_title((view.get("title") or "Audio lesson").strip())
    header_bottom = MARGIN + logo_size + 40
    audio_top = HEIGHT - 150
    font, lines, line_h = _fit_title(draw, title, WIDTH - 2 * MARGIN, audio_top - header_bottom)
    block_h = len(lines) * line_h
    ty = header_bottom + (audio_top - header_bottom - block_h) // 2
    for i, line in enumerate(lines):
        draw.text((MARGIN, ty + i * line_h), line, font=font, fill=INK)

    # --- Wordless audio cue: play button + full-width soundform ---
    by = HEIGHT - MARGIN - 46
    _play(draw, MARGIN + 32, by + 22, 30, ORANGE_DEEP)
    wave_x = MARGIN + 90
    _waveform(draw, wave_x, by, WIDTH - MARGIN - wave_x, 44, ORANGE)

    return img


def cached_card_path(data_folder, lesson_id):
    return os.path.join(data_folder, "og-images", "shared-lessons", f"{lesson_id}.png")


def ensure_cached_card(view, data_folder):
    """Render (once) and cache the card PNG for this lesson; return its path.
    Returns None if the view has no lesson_id to key the cache on."""
    lesson_id = view.get("lesson_id")
    if not lesson_id:
        return None
    path = cached_card_path(data_folder, lesson_id)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        render_card(view).save(path, format="PNG")
    return path


# --- Article cards: just the article's own photo, cover-cropped -------------
# The headline / level / reading time / source — and "zeeguu.org" — all render
# natively in the link's text block, at the reader's own font size. So nothing
# is baked onto the image: device-text is always crisper at thumbnail size and
# scales per-phone, where baked text can't. The image is purely the photo.

def _cover(image, target_w, target_h):
    """Scale to fill (target_w, target_h) and centre-crop — never distorts."""
    iw, ih = image.size
    scale = max(target_w / iw, target_h / ih)
    image = image.resize((max(1, round(iw * scale)), max(1, round(ih * scale))))
    nw, nh = image.size
    left, top = (nw - target_w) // 2, (nh - target_h) // 2
    return image.crop((left, top, left + target_w, top + target_h))


def render_article_card(view, photo=None):
    """The article's photo, cover-cropped to the OG ratio — purely visual.
    Falls back to a plain Zeeguu brand card when there's no photo (rare); the
    article's text lives in the link's og:title / og:description either way."""
    if photo is not None:
        return _cover(photo.convert("RGB"), WIDTH, HEIGHT)

    img = _gradient_bg()
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 12, HEIGHT), fill=ORANGE)
    try:
        size = 150
        logo = Image.open(_LOGO_PATH).convert("RGBA").resize((size, size))
        img.paste(logo, ((WIDTH - size) // 2, HEIGHT // 2 - size - 6), logo)
    except OSError:
        pass
    wordmark = _font("ExtraBold", 60)
    tw = draw.textlength("Zeeguu", font=wordmark)
    draw.text(((WIDTH - tw) // 2, HEIGHT // 2 + 24), "Zeeguu", font=wordmark, fill=ORANGE_DEEP)
    return img


def cached_article_card_path(data_folder, article_id):
    # JPEG, not PNG: the card embeds a photo, so JPEG is ~5x smaller — crawlers
    # fetch it faster and are far less likely to skip it on a cold first scrape.
    return os.path.join(data_folder, "og-images", "shared-articles", f"{article_id}.jpg")


def ensure_cached_article_card(view, data_folder, photo=None):
    """Render (once) and cache the article card JPEG; return its path, or None if
    the view has no article_id."""
    article_id = view.get("article_id")
    if not article_id:
        return None
    path = cached_article_card_path(data_folder, article_id)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        render_article_card(view, photo).save(path, format="JPEG", quality=85, optimize=True)
    return path

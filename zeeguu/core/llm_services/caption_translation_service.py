"""Translate a video's captions into the learner's target language at their CEFR level.

Per-segment translation preserves the original `time_start`/`time_end` of each `Caption`, so
the player's timing logic is unchanged — only the rendered text and tokenization differ.

LLM strategy: batches of ~30 captions per Haiku call (cheap and fast), structured JSON output
keyed by numeric marker; on parse / missing-key failure we fall back to a single-caption call
for the affected items so partial LLM failures degrade gracefully instead of zeroing the set.
"""
from __future__ import annotations

import json
import re
from typing import Iterable, Optional

from zeeguu.core.model.db import db
from zeeguu.core.model.caption import Caption
from zeeguu.core.model.caption_translation import CaptionTranslation
from zeeguu.core.model.caption_translation_set import CaptionTranslationSet
from zeeguu.core.llm_services.haiku_client import haiku_completion
from zeeguu.logging import log


BATCH_SIZE = 30
BATCH_MAX_TOKENS = 2000  # generous; ~30 short captions translated easily fit
SINGLE_MAX_TOKENS = 200


def _batched(items, n):
    for i in range(0, len(items), n):
        yield items[i : i + n]


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _build_batch_prompt(
    captions: list[Caption], source_language: str, target_language: str, cefr: str
) -> str:
    numbered = "\n".join(f"[{i + 1}] {c.get_content()}" for i, c in enumerate(captions))
    return f"""Translate each of the following {source_language} subtitle lines into {target_language} at CEFR level {cefr}.

Rules:
- Preserve meaning faithfully; favor natural, idiomatic {target_language}.
- Adapt vocabulary and grammar to CEFR {cefr} (simpler words for A1-A2, intermediate for B1-B2, advanced for C1-C2).
- One line per input line — do NOT merge or split lines.
- Output STRICTLY a single JSON object, nothing else (no markdown fences, no commentary):
{{"1": "translation of line 1", "2": "translation of line 2", ...}}

Lines to translate:
{numbered}
"""


def _build_single_prompt(
    text: str, source_language: str, target_language: str, cefr: str
) -> str:
    return (
        f"Translate the following {source_language} subtitle into {target_language} "
        f"at CEFR level {cefr}. Output ONLY the translation — no quotes, no commentary.\n\n"
        f"{text}"
    )


def _translate_batch(
    captions: list[Caption], source_language: str, target_language: str, cefr: str
) -> dict[int, str]:
    """Returns {1-based index in `captions` -> translation}. Missing keys mean the LLM didn't
    provide a translation for that line; callers should fall back per-caption for those."""
    if not captions:
        return {}
    prompt = _build_batch_prompt(captions, source_language, target_language, cefr)
    raw = haiku_completion(prompt, max_tokens=BATCH_MAX_TOKENS, temperature=0.1)
    if not raw:
        return {}
    try:
        # `strict=False` because LLMs sometimes embed literal newlines in JSON string values
        # (which `json.loads` strict mode rejects). Matches the simplification_service fix.
        parsed = json.loads(_strip_code_fence(raw), strict=False)
    except (json.JSONDecodeError, ValueError) as e:
        log(f"[caption_translation] batch JSON parse failed: {e}")
        return {}
    if not isinstance(parsed, dict):
        return {}
    out: dict[int, str] = {}
    for k, v in parsed.items():
        try:
            idx = int(str(k).strip())
        except ValueError:
            continue
        if isinstance(v, str) and v.strip():
            out[idx] = v.strip()
    return out


def _translate_one(
    text: str, source_language: str, target_language: str, cefr: str
) -> Optional[str]:
    raw = haiku_completion(
        _build_single_prompt(text, source_language, target_language, cefr),
        max_tokens=SINGLE_MAX_TOKENS,
        temperature=0.1,
    )
    if not raw:
        return None
    cleaned = raw.strip().strip('"').strip()
    return cleaned or None


def translate_set(set_id: int) -> None:
    """Background-job entry point. Translates every caption in the set's video and stores the
    rows. Idempotent at the row level: existing CaptionTranslations for the set are skipped so
    a retried run resumes instead of duplicating."""
    translation_set = CaptionTranslationSet.find_by_id(set_id)
    if translation_set is None:
        log(f"[caption_translation] no set with id {set_id}")
        return

    try:
        translation_set.mark_translating()
        db.session.commit()

        video = translation_set.video
        source_language = video.language.code
        target_language = translation_set.target_language.code
        cefr = translation_set.cefr_level

        captions = sorted(video.captions, key=lambda c: c.time_start)
        if not captions:
            translation_set.mark_error("Video has no captions to translate.")
            db.session.commit()
            return

        already_done = {
            ct.caption_id
            for ct in CaptionTranslation.query.filter_by(set_id=translation_set.id).all()
        }
        todo = [c for c in captions if c.id not in already_done]
        log(
            f"[caption_translation] set={translation_set.id} translating "
            f"{len(todo)}/{len(captions)} captions ({source_language} -> {target_language}, {cefr})"
        )

        for batch in _batched(todo, BATCH_SIZE):
            batch_translations = _translate_batch(
                batch, source_language, target_language, cefr
            )
            for i, caption in enumerate(batch, start=1):
                text = batch_translations.get(i)
                if not text:
                    # Per-caption fallback for items the batch call dropped or mis-keyed.
                    text = _translate_one(
                        caption.get_content(), source_language, target_language, cefr
                    )
                if not text:
                    # Last resort: skip this caption rather than fail the whole set; the
                    # reader will show the original text for un-translated lines.
                    log(
                        f"[caption_translation] dropped caption {caption.id} "
                        f"(set={translation_set.id}) — LLM returned nothing"
                    )
                    continue
                CaptionTranslation.create(
                    db.session, translation_set, caption, text
                )
            db.session.commit()

        translation_set.mark_ready()
        db.session.commit()
        log(f"[caption_translation] set={translation_set.id} ready")
    except Exception as e:  # noqa: BLE001 — background job; surface via status row
        log(f"[caption_translation] set={set_id} error: {e}")
        db.session.rollback()
        # Reload after rollback to mark the set's error state cleanly.
        translation_set = CaptionTranslationSet.find_by_id(set_id)
        if translation_set:
            translation_set.mark_error(str(e))
            db.session.commit()

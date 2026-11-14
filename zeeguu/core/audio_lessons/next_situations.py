"""
The situations an A0 learner could move on to after a lesson.

An A0 learner's daily lessons stay in the situation they chose until they
choose another. Mayar moved on herself; Marvel had eleven lessons in "grocery
shopping" (Nov 2026), because nothing in the app offered a next step. So when
an A0 lesson is generated, the model also suggests three next situations,
knowing the ones the learner already had; the app offers them when the lesson
ends, next to "stay here". They are suggested at generation time, so the
learner does not wait for them; a failure leaves the lesson without them.
"""

import json
import re
from collections import Counter

from zeeguu.core.audio_lessons.script_generator import get_prompt_template
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
from zeeguu.core.model.language import Language
from zeeguu.logging import log

PROMPT = "a0_next_situations-v1.txt"
HOW_MANY = 3


def past_situations(user, language):
    """[(situation, lesson count)] of the learner's lessons in this language,
    in the order they first had them."""
    lessons = (
        DailyAudioLesson.query.filter_by(user_id=user.id, language_id=language.id)
        .order_by(DailyAudioLesson.id)
        .all()
    )
    names = [l.canonical_suggestion for l in lessons if l.canonical_suggestion]
    counts = Counter(names)
    return [(name, counts[name]) for name in dict.fromkeys(names)]


def lessons_per_situation(user, language):
    """[{raw_suggestion, canonical_suggestion, lessons}] of the learner's
    lessons in this language, for the settings dialog to show next to each
    situation how many lessons they have had in it."""
    from sqlalchemy import func

    rows = (
        DailyAudioLesson.query.filter(
            DailyAudioLesson.user_id == user.id,
            DailyAudioLesson.language_id == language.id,
            DailyAudioLesson.canonical_suggestion.isnot(None),
        )
        .with_entities(
            DailyAudioLesson.raw_suggestion,
            DailyAudioLesson.canonical_suggestion,
            func.count(DailyAudioLesson.id),
        )
        .group_by(DailyAudioLesson.raw_suggestion, DailyAudioLesson.canonical_suggestion)
        .all()
    )
    return [
        {"raw_suggestion": raw, "canonical_suggestion": canonical, "lessons": n}
        for raw, canonical, n in rows
    ]


def parse_suggestions(text, already_had=()):
    """The model's JSON array, cleaned: strings only, no repeats, none the
    learner already had, at most HOW_MANY. Raises on anything not a JSON array."""
    # A code fence around the answer, on its own lines or on the same line.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    items = json.loads(text)
    if not isinstance(items, list):
        raise ValueError(f"not a list: {text[:200]!r}")
    had = {h.strip().lower() for h in already_had}
    result = []
    for item in items:
        if not isinstance(item, str):
            continue
        name = item.strip().strip(".").lower()[:80]
        if name and name not in had and name not in result:
            result.append(name)
    return result[:HOW_MANY]


def suggest_next_situations(user, language, current_situation):
    """Up to three situation names in the learner's native language, or []."""
    from zeeguu.core.llm_services import get_llm_service

    past = past_situations(user, language)
    native = user.native_language.name if user.native_language else "English"
    prompt = get_prompt_template(PROMPT).format(
        target_language=Language.LANGUAGE_NAMES.get(language.code, language.code),
        native_language=native,
        past_situations="\n".join(f"- {name} ({n})" for name, n in past) or "- none yet",
        current_situation=current_situation,
    )
    try:
        answer = get_llm_service("unified").generate_text(prompt, max_tokens=150, temperature=0.7)
        return parse_suggestions(answer, [name for name, _ in past] + [current_situation])
    except Exception as e:
        log(f"[next_situations] user {user.id}, after '{current_situation}': {e}")
        return []

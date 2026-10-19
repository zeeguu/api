"""
The words an A0 lesson taught the learner to say, scheduled for exercises once
they have heard it.

An A0 lesson teaches two kinds of words: those of the learner's own role, which
they learn to SAY (said slowly, then asked for with "How do you say ...?"), and
those of the other person, which they only learn to understand. The first kind
goes on their study list, with the dialogue line it comes from as its context,
so the exercises keep what the audio taught. See
future-work/a0-audio-lessons.md in the docs repo.
"""

import json
import re

from zeeguu.core.model.language import Language
from zeeguu.logging import log

_PROMPT = """Below is an audio lesson for an absolute beginner learning {target_language}. The Teacher speaks {source_language}.

The lesson taught the learner to SAY some words or short chunks: the Teacher explained each one, it was said slowly (marked [slow]), and then the Teacher asked for it ("How do you say ...?"). List exactly those, each once, as the Teacher introduced them -- not the full sentences built from them later, and not the other person's lines, which the learner only had to understand.

For each, give:
- "word": as the learner says it, in {target_language}, written exactly as in the script
- "translation": what it means, in {source_language}, as short as the Teacher put it
- "sentence": a line of the dialogue at the start of the lesson that contains the word exactly once, copied exactly without the speaker label and the [..] markers; if no dialogue line contains it, the word itself

Output only a JSON list: [{{"word": "...", "translation": "...", "sentence": "..."}}]

LESSON:
{script}"""


def _first_json_list(text):
    """The first JSON list of objects in `text`: the answer may have prose, or a
    bracket like [slow], before it."""
    decoder = json.JSONDecoder()
    for start in (i for i, ch in enumerate(text or "") if ch == "["):
        try:
            value, _ = decoder.raw_decode(text[start:])
        except ValueError:
            continue
        # Not an empty list: "[]" in the prose is not the answer.
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            return value
    return None


def _text(value):
    # A JSON null must not become the string "None".
    return value.strip() if isinstance(value, str) else ""


def words_taught_to_say(dialogue):
    """
    [(word, translation, sentence)] for an AudioLessonDialogue that builds on
    history. Empty when the model's answer cannot be read.
    """
    from zeeguu.core.llm_services.llm_service import get_llm_service

    prompt = _PROMPT.format(
        target_language=Language.LANGUAGE_NAMES.get(dialogue.language.code, dialogue.language.code),
        source_language=Language.LANGUAGE_NAMES.get(
            dialogue.teacher_language.code, dialogue.teacher_language.code
        ),
        script=dialogue.script,
    )
    answer = get_llm_service("unified").generate_text(prompt, max_tokens=2000, temperature=0.0)

    items = _first_json_list(answer)
    if items is None:
        log(f"[lesson_words] dialogue {dialogue.id}: unreadable answer {(answer or '')[:200]!r}")
        return []

    words = []
    for item in items:
        word, translation = _text(item.get("word")), _text(item.get("translation"))
        if word and translation:
            words.append((word, translation, _text(item.get("sentence")) or word))
    return words


def _context_for(word, sentence, language):
    """The dialogue line if the word is in it exactly once, else the word on its
    own, else None. Decided before anything is created: what add_word_to_study
    creates is committed and cannot be taken back."""
    from zeeguu.core.bookmark_operations.add_word_to_study import (
        WordNotInContext,
        word_position_in,
    )

    for context in dict.fromkeys([sentence, word]):
        try:
            word_position_in(word, context, language)
            return context
        except WordNotInContext:
            continue
    return None


def schedule_words_from_lesson(db_session, user, dialogue):
    """
    Put the words the lesson taught the learner to say on their study list.
    Words they already have are left as they are. Returns how many were added.
    """
    from zeeguu.core.bookmark_operations.add_word_to_study import add_word_to_study

    added = 0
    for word, translation, sentence in words_taught_to_say(dialogue):
        context = _context_for(word, sentence, dialogue.language)
        if context is None:
            log(f"[lesson_words] dialogue {dialogue.id}: '{word}' not found in '{sentence}', skipped")
            continue
        try:
            result = add_word_to_study(
                db_session,
                user,
                word,
                translation,
                dialogue.language.code,
                dialogue.teacher_language.code,
                context,
                from_audio_lesson=True,
            )
            if result and result[2] is not None:
                added += 1
        except Exception as e:
            db_session.rollback()
            log(f"[lesson_words] dialogue {dialogue.id}: '{word}' not added: {e}")
    db_session.commit()
    log(f"[lesson_words] dialogue {dialogue.id}: {added} words scheduled for user {user.id}")
    return added


def schedule_words_after_lesson(user_id, lesson_id):
    """
    For run_in_background, when a lesson is completed for the first time: the
    model call takes seconds, and the learner's "complete" request does not wait
    for it. Takes ids: it runs in its own session.
    """
    from zeeguu.core.model import db, User
    from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson

    user = User.find_by_id(user_id)
    lesson = DailyAudioLesson.query.get(lesson_id)
    if not user or not lesson:
        return
    for segment in lesson.segments:
        dialogue = segment.audio_lesson_dialogue
        if dialogue is not None and dialogue.builds_on_history and dialogue.teacher_language:
            schedule_words_from_lesson(db.session, user, dialogue)

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

    match = re.search(r"\[.*\]", answer or "", re.DOTALL)
    try:
        items = json.loads(match.group(0)) if match else []
    except ValueError:
        log(f"[lesson_words] dialogue {dialogue.id}: unreadable answer {answer[:200]!r}")
        return []

    words = []
    for item in items:
        if not isinstance(item, dict):
            continue
        word = str(item.get("word", "")).strip()
        translation = str(item.get("translation", "")).strip()
        sentence = str(item.get("sentence", "")).strip() or word
        if word and translation:
            words.append((word, translation, sentence))
    return words


def schedule_words_from_lesson(db_session, user, dialogue):
    """
    Put the words the lesson taught the learner to say on their study list.
    Returns how many were added. A word that cannot be anchored in its sentence
    is tried with itself as the context; one that still fails is skipped, and a
    failure never undoes the others.
    """
    from zeeguu.core.bookmark_operations.add_word_to_study import (
        WordNotInContext,
        add_word_to_study,
    )

    added = 0
    for word, translation, sentence in words_taught_to_say(dialogue):
        for context in dict.fromkeys([sentence, word]):
            savepoint = db_session.begin_nested()
            try:
                add_word_to_study(
                    db_session,
                    user,
                    word,
                    translation,
                    dialogue.language.code,
                    dialogue.teacher_language.code,
                    context,
                )
                savepoint.commit()
                added += 1
                break
            except WordNotInContext:
                savepoint.rollback()
            except Exception as e:
                savepoint.rollback()
                log(f"[lesson_words] dialogue {dialogue.id}: '{word}' not added: {e}")
                break
    log(f"[lesson_words] dialogue {dialogue.id}: {added} words scheduled for user {user.id}")
    return added

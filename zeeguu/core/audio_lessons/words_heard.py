"""
Which words of the learned language a user has heard in their audio lessons.

Counted from the scripts themselves -- the lines the Man, the Woman and the
teacher's target-language voice (TeacherL2) actually say -- not from a list of
words a prompt claims to have taught: a model that slips in extra words still
shows up here, and the next lesson builds on what was really said.

Used by lessons that build on the learner's history (A0): the table goes into the
prompt, and the model plans the next lesson from it the way Pimsleur does --
words from the last few lessons come back often, older ones now and then, few
new ones are added. Design: future-work/a0-audio-lessons.md in the docs repo.
"""

import re
from collections import Counter, namedtuple

from sqlalchemy.orm import selectinload

from zeeguu.core.audio_lessons.script_parser import parse_script
from zeeguu.core.audio_lessons.script_language_validator import TARGET_LANGUAGE_VOICES

HeardLesson = namedtuple("HeardLesson", ["title", "words"])

_TIMING = re.compile(r"\[[^\]]*\]")
_WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")


def target_language_words(script: str) -> Counter:
    """How often each word is said in the learned language, lowercased."""
    words = Counter()
    for voice, text, _ in parse_script(script or ""):
        if voice not in TARGET_LANGUAGE_VOICES:
            continue
        words.update(w.lower() for w in _WORD.findall(_TIMING.sub(" ", text)))
    return words


def _history_lessons(user, language):
    """
    The user's daily lessons in `language` made of a dialogue that builds on
    their history, newest first.

    Only those: a word lesson is cached and shared across users by word and
    written at whatever level it was first written at, so its vocabulary says
    nothing about what this beginner was taught.
    """
    from zeeguu.core.model.audio_lesson_dialogue import AudioLessonDialogue
    from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
    from zeeguu.core.model.daily_audio_lesson_segment import DailyAudioLessonSegment

    return (
        DailyAudioLesson.query.join(
            DailyAudioLessonSegment,
            DailyAudioLessonSegment.daily_audio_lesson_id == DailyAudioLesson.id,
        )
        .join(
            AudioLessonDialogue,
            DailyAudioLessonSegment.audio_lesson_dialogue_id == AudioLessonDialogue.id,
        )
        .filter(
            DailyAudioLesson.user_id == user.id,
            DailyAudioLesson.language_id == language.id,
            AudioLessonDialogue.builds_on_history.is_(True),
        )
        .distinct()
        .order_by(DailyAudioLesson.created_at.desc())
    )


def history_lesson_count(user, language) -> int:
    """How many lessons built on their history the user has been given in `language`."""
    return _history_lessons(user, language).count()


def heard_lessons(user, language, limit=30) -> list:
    """
    The user's lessons built on their history in `language` that they engaged
    with, oldest first, with the words each one said. The most recent `limit` of
    the ones they engaged with: lessons never played do not take up the window.

    Engaged = DailyAudioLesson.is_engaged: finished, or listened at least
    halfway. A lesson generated but never played was not heard.
    """
    from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
    from zeeguu.core.model.daily_audio_lesson_segment import DailyAudioLessonSegment

    lessons = (
        _history_lessons(user, language)
        .options(
            selectinload(DailyAudioLesson.segments).selectinload(
                DailyAudioLessonSegment.audio_lesson_dialogue
            )
        )
        .all()
    )
    # is_engaged is computed in Python, so the window is applied after it.
    engaged = [lesson for lesson in lessons if lesson.is_engaged][:limit]

    heard = []
    for lesson in reversed(engaged):
        words = Counter()
        for segment in lesson.segments:
            if segment.audio_lesson_dialogue is not None:
                words.update(target_language_words(segment.audio_lesson_dialogue.script))
        if words:
            heard.append(HeardLesson(lesson.display_title(), words))
    return heard


def history_table(heard: list) -> str:
    """
    The heard lessons as text for a prompt: the lessons in order, then one row
    per word with the lessons it came up in and how often, most recent first.

        Lesson 1: At the café
        Lesson 2: Asking for directions

        word        heard in lesson (times)
        undskyld    2 (6), 1 (14)
    """
    if not heard:
        return ""

    lines = [f"Lesson {i}: {lesson.title or 'untitled'}" for i, lesson in enumerate(heard, 1)]
    lines.append("")

    seen_in = {}
    for i, lesson in enumerate(heard, 1):
        for word, count in lesson.words.items():
            seen_in.setdefault(word, []).append((i, count))

    # Most recently heard first, then most heard: the words the next lesson
    # should lean on come out on top.
    rows = sorted(
        seen_in.items(),
        key=lambda item: (-item[1][-1][0], -sum(c for _, c in item[1]), item[0]),
    )
    width = max(len(word) for word in seen_in) + 2
    lines.append(f"{'word'.ljust(width)}heard in lesson (times)")
    for word, occurrences in rows:
        where = ", ".join(f"{i} ({c})" for i, c in reversed(occurrences))
        lines.append(f"{word.ljust(width)}{where}")
    return "\n".join(lines)

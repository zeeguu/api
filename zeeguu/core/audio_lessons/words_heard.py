"""
Which words of the learned language a user has heard in their audio lessons.

Counted from the scripts themselves -- the lines the Man, the Woman and the
teacher's target-language voice (TeacherL2) actually say -- not from a list of
words a prompt claims to have taught: a model that slips in extra words still
shows up here, and the next lesson builds on what was really said.

Used by lessons that build on the learner's history (A0): the table goes into the
prompt, and the model plans the next lesson from it the way Pimsleur does --
words from the last few lessons come back often, older ones now and then, few
new ones are added. See docs/future-work/a0-audio-lessons.md.
"""

import re
from collections import Counter, namedtuple

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
    return _without_fragments(words)


def _without_fragments(words: Counter) -> Counter:
    """
    Drop the pieces a new word is built up from ("undskyld" is said as "skyld",
    "und", "undskyld"): each is said once or twice, inside a longer word of the
    same script. Left in, the history would list "und" as a word the learner
    knows. A real short word ("en" in "kaffen") is said far more often.
    """
    return Counter(
        {
            word: count
            for word, count in words.items()
            if count > 2 or not any(word != other and word in other for other in words)
        }
    )


def heard_lessons(user, language, limit=30) -> list:
    """
    The user's audio lessons in `language` that they engaged with, oldest first,
    with the words each one said. The most recent `limit` of them.

    Engaged = DailyAudioLesson.is_engaged: finished, or listened at least
    halfway. A lesson generated but never played was not heard.
    """
    from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson

    lessons = (
        DailyAudioLesson.query.filter_by(user_id=user.id, language_id=language.id)
        .order_by(DailyAudioLesson.created_at.desc())
        .limit(limit)
        .all()
    )

    heard = []
    for lesson in reversed(lessons):
        if not lesson.is_engaged:
            continue
        words = Counter()
        for segment in lesson.segments:
            content = segment.audio_lesson_dialogue or segment.audio_lesson_meaning
            if content is not None:
                words.update(target_language_words(content.script))
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

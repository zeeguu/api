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

# dialogue: the lesson's dialogue as [(voice, text)], voice "man" or "woman";
# learner: the voice the learner played. Both empty when not found.
HeardLesson = namedtuple(
    "HeardLesson", ["title", "words", "dialogue", "learner"], defaults=((), None)
)

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


def dialogue_and_learner(script: str):
    """
    The dialogue an A0 lesson is built around, and the voice the learner played.

    The dialogue is the last run of Man/Woman lines: the lesson ends by playing
    it again (step 7 of the prompt). The opening one is no better: in 62 of 63
    prod lessons (20 Nov 2026) they were the same, and in the other the opening
    had a stray line. The learner is the voice heard most: their lines are
    drilled and recalled, the other person's only understood, so in those 63
    lessons the learner's voice had 1.6x to 6.5x the lines.
    """
    runs, run = [], []
    lines = Counter()
    for voice, text, _ in parse_script(script or ""):
        if voice == "silence":
            continue
        if voice in ("man", "woman"):
            run.append((voice, text))
            lines[voice] += 1
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)
    if not runs:
        return (), None
    return tuple(runs[-1]), lines.most_common(1)[0][0]


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
        dialogue, learner = (), None
        for segment in lesson.segments:
            if segment.audio_lesson_dialogue is not None:
                script = segment.audio_lesson_dialogue.script
                words.update(target_language_words(script))
                dialogue, learner = dialogue_and_learner(script)
        if words:
            heard.append(HeardLesson(lesson.display_title(), words, dialogue, learner))
    return heard


def earlier_dialogues(heard: list, count: int) -> str:
    """
    The dialogues of the learner's latest lessons, for rehearsal at the end of
    the next one, newest first, each with the role the learner played in it:

        Lesson 4: Buying a bus ticket (the learner was the Man)
        Man: Hej. Jeg skal have en billet, tak.
        Woman: Hvor skal du hen?
    """
    parts = []
    if count <= 0:
        return ""
    for i in range(len(heard), 0, -1):
        lesson = heard[i - 1]
        if not lesson.dialogue or not lesson.learner:
            continue
        lines = [f"Lesson {i}: {lesson.title or 'untitled'} (the learner was the {lesson.learner.capitalize()})"]
        lines += [f"{voice.capitalize()}: {text}" for voice, text in lesson.dialogue]
        parts.append("\n".join(lines))
        if len(parts) >= count:
            break
    return "\n\n".join(parts)


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

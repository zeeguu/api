"""
Tuning a learner's next A0 lessons from what they said about the earlier ones.

After a lesson the learner can say, for each of three aspects, that it should
go one way, the other way, or stay as it was (AudioLessonFeedback). Each aspect
is a level from -2 to +2, starting at 0 (the lesson as it was before tuning
existed). Walking through the learner's lessons from the oldest, every answer
moves the level one step, and the level stays within -2..+2 at every step: so
after "faster" three times, one "slower" already slows the next lesson down.
"Just right" leaves the level where it is.

The levels fill in the numbers of the A0 lesson prompt (prompt_values). Only
A0 lessons are tuned: the other levels' prompts have no such numbers.
"""

from dataclasses import dataclass

from zeeguu.core.model.audio_lesson_feedback import AudioLessonFeedback

LEVELS = (-2, -1, 0, 1, 2)

# aspect -> {value: step}. A positive step is a faster, less repetitive lesson
# with more new words.
ASPECTS = {
    "pace": {"slower": -1, "just_right": 0, "faster": 1},
    "repetition": {"more": -1, "just_right": 0, "less": 1},
    "new_words": {"fewer": -1, "just_right": 0, "more": 1},
}

SITUATION = "situation"
STAY = "stay"


@dataclass(frozen=True)
class LessonTuning:
    pace: int = 0
    repetition: int = 0
    new_words: int = 0


def tuning_from(rows) -> LessonTuning:
    """rows: AudioLessonFeedback rows, oldest lesson first."""
    levels = {aspect: 0 for aspect in ASPECTS}
    for row in rows:
        step = ASPECTS.get(row.aspect, {}).get(row.value)
        if step:
            levels[row.aspect] = max(-2, min(2, levels[row.aspect] + step))
    return LessonTuning(**levels)


def tuning_for(user, language) -> LessonTuning:
    return tuning_from(AudioLessonFeedback.history(user, language.id))


# The prompt's numbers per level, -2..+2. Level 0 is the prompt as it was (v1).
# pace: the pause after a challenge, for the learner to answer, and the pause
# after each repetition.
_ANSWER_PAUSE = (7, 6, 5, 4, 3)
_REPEAT_PAUSE = (4, 4, 3, 3, 2)
# repetition (+ is less): how often a word to say, and a line to understand,
# comes back in the recalls; how often a new word is said at normal speed after
# the slow time; and the lesson's longest length, in lines.
_RECALLS_TO_SAY = (7, 6, 5, 4, 2)
_RECALLS_TO_UNDERSTAND = (4, 4, 3, 2, 1)
_NORMAL_SPEED_REPEATS = ("twice", "twice", "twice", "twice", "once")
_MAX_LINES = (200, 200, 200, 160, 120)
# new_words: the dialogue the lesson is built around. Its lines are where the
# new words come from, so more lines means more new words.
_DIALOGUE_LINES = ((2, 3), (2, 4), (2, 6), (3, 7), (4, 8))

# 200 lines measured about 12 minutes.
_SECONDS_PER_LINE = 12 * 60 / 200


def prompt_values(tuning: LessonTuning) -> dict:
    p, r, n = tuning.pace + 2, tuning.repetition + 2, tuning.new_words + 2
    max_lines = _MAX_LINES[r]
    return dict(
        answer_pause=_ANSWER_PAUSE[p],
        repeat_pause=_REPEAT_PAUSE[p],
        recalls_to_say=_RECALLS_TO_SAY[r],
        recalls_to_understand=_RECALLS_TO_UNDERSTAND[r],
        normal_speed_repeats=_NORMAL_SPEED_REPEATS[r],
        max_lines=max_lines,
        max_minutes=round(max_lines * _SECONDS_PER_LINE / 60),
    )


def dialogue_line_range(tuning: LessonTuning) -> tuple:
    return _DIALOGUE_LINES[tuning.new_words + 2]


def is_valid(aspect, value, lesson=None) -> bool:
    """Whether the app may record this answer. A situation must be "stay" or
    one of the situations the lesson suggested."""
    if aspect in ASPECTS:
        return value in ASPECTS[aspect]
    if aspect == SITUATION:
        return value == STAY or bool(
            lesson is not None and lesson.next_situations and value in lesson.next_situations
        )
    return False

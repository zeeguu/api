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

Length is not a level but the learner's setting, in minutes
(UserPreference.AUDIO_LESSON_MINUTES), which they see and can set themselves:
"too short" and "too long" move it one step (lesson_minutes_after). The prompt
asks for a lesson between that length and a few minutes more, and fills it
with rehearsal of the learner's earlier dialogues when the new words alone are
done sooner: a lesson that came out shorter than asked made one learner miss
their 10-minute daily goal (20 Nov 2026).
"""

from dataclasses import asdict, dataclass

from zeeguu.core.model.audio_lesson_feedback import AudioLessonFeedback

LEVELS = (-2, -1, 0, 1, 2)

# aspect -> {value: step}. A positive step is a faster, less repetitive,
# shorter lesson.
ASPECTS = {
    "pace": {"slower": -1, "just_right": 0, "faster": 1},
    "repetition": {"more": -1, "just_right": 0, "less": 1},
    "length": {"longer": -1, "just_right": 0, "shorter": 1},
}

SITUATION = "situation"
STAY = "stay"


@dataclass(frozen=True)
class LessonTuning:
    pace: int = 0
    repetition: int = 0
    length: int = 0


def tuning_from(rows) -> LessonTuning:
    """rows: AudioLessonFeedback rows, oldest lesson first."""
    levels = {aspect: 0 for aspect in ASPECTS}
    for row in rows:
        step = ASPECTS.get(row.aspect, {}).get(row.value)
        if step:
            levels[row.aspect] = max(LEVELS[0], min(LEVELS[-1], levels[row.aspect] + step))
    return LessonTuning(**levels)


def tuning_for(user, language) -> LessonTuning:
    return tuning_from(AudioLessonFeedback.history(user, language.id))


def as_dict(tuning: LessonTuning) -> dict:
    return asdict(tuning)


# The prompt's numbers per level, -2..+2. Level 0 is the prompt as it was (v1).
# pace: the pause after a challenge, for the learner to answer, and the pause
# after each repetition.
_ANSWER_PAUSE = (7, 6, 5, 4, 3)
_REPEAT_PAUSE = (4, 4, 3, 3, 2)
# repetition (+ is less): how often a word to say, and a line to understand,
# comes back in the recalls; how often a new word is said at normal speed after
# the slow time; and how often words from the latest earlier lessons come back.
# A learner who finds a lesson repetitive does not care whether the word was
# new today: "tak" and "hej" from earlier lessons were what one participant
# heard too often.
_RECALLS_TO_SAY = (7, 6, 5, 4, 2)
_RECALLS_TO_UNDERSTAND = (4, 4, 3, 2, 1)
_NORMAL_SPEED_REPEATS = (2, 2, 2, 2, 1)
_TIMES = {1: "once", 2: "twice", 3: "three times"}
_EARLIER_WORDS_RECALLS = (
    "many times", "several times", "several times", "two or three times", "once",
)
# The length the learner can choose, in minutes, and the step "too short" and
# "too long" move it by.
# 25 at most for now: asked for 30, Sonnet 5.5 wrote 24 minutes, running out
# of material (eval zeeguu-experiments audio-lessons/2026-11-20-a0-length-rehearsal).
# Script functions that code expands would bring 30 back
# (docs future-work/a0-lesson-script-functions.md).
LESSON_MINUTES_CHOICES = (5, 10, 15, 20, 25)
LESSON_MINUTES_STEP = 5
# How much longer than the chosen length a lesson may run; never past the
# longest choice, which is a hard cap: a 25-minute lesson is asked for 22-25.
_LESSON_MINUTES_MARGIN = 3
MAX_LESSON_MINUTES = LESSON_MINUTES_CHOICES[-1]

# 63 A0 lessons in prod (20 Nov 2026): 4.9-6.8 seconds per voice line,
# median 5.5. The earlier estimate, 200 lines in 12 minutes, was 3.6.
_SECONDS_PER_LINE = 5.5


# The shortest default: about what A0 lessons were before the length was a
# setting (median 10.6 minutes over 63 lessons). A learner on the default
# 5-minute goal, or the grandfathered 2, keeps that length unless they choose
# a shorter one: 5 of 12 A0 learners on 20 Nov 2026.
DEFAULT_LESSON_MINUTES = 10


def default_lesson_minutes(daily_goal_minutes, length_level=0) -> int:
    """
    The lesson length of a learner who has not set one: their daily goal, so
    that a lesson heard to the end is the day's goal reached, but never under
    DEFAULT_LESSON_MINUTES. length_level is from "too short" / "too long"
    answered before the length was a setting, each a step.
    """
    base = max(daily_goal_minutes, DEFAULT_LESSON_MINUTES)
    return _snap(base - length_level * LESSON_MINUTES_STEP)


def lesson_minutes_after(minutes, value) -> int:
    """The length after a "longer" / "shorter" / "just_right" answer."""
    return _snap(minutes - ASPECTS["length"].get(value, 0) * LESSON_MINUTES_STEP)


def _snap(minutes) -> int:
    return min(LESSON_MINUTES_CHOICES, key=lambda choice: abs(choice - minutes))


def lesson_minutes_for(user, language) -> int:
    from zeeguu.core.model.user_preference import UserPreference

    chosen = UserPreference.get_audio_lesson_minutes(user)
    if chosen:
        return chosen
    return default_lesson_minutes(
        UserPreference.get_daily_goal_minutes(user), tuning_for(user, language).length
    )


def lines_for(minutes) -> int:
    return round(minutes * 60 / _SECONDS_PER_LINE)


def dialogues_to_rehearse(minutes) -> int:
    """
    How many earlier dialogues the lesson rehearses: the length comes from
    them. Asked for 20 minutes in lines alone, Sonnet 5.5 wrote 12-14 (eval
    zeeguu-experiments audio-lessons/2026-11-20-a0-length-rehearsal); a
    lesson's own new words fill about 10, and each dialogue rehearsed adds a
    few minutes.
    """
    return max(0, min(8, (minutes - 5) // 5 * 2))


def prompt_values(tuning: LessonTuning, minutes: int) -> dict:
    p, r = tuning.pace + 2, tuning.repetition + 2
    max_minutes = min(minutes + _LESSON_MINUTES_MARGIN, MAX_LESSON_MINUTES)
    min_minutes = min(minutes, max_minutes - _LESSON_MINUTES_MARGIN)
    return dict(
        answer_pause=_ANSWER_PAUSE[p],
        repeat_pause=_REPEAT_PAUSE[p],
        recalls_to_say=_RECALLS_TO_SAY[r],
        recalls_to_understand=_RECALLS_TO_UNDERSTAND[r],
        normal_speed_repeats=_TIMES[_NORMAL_SPEED_REPEATS[r]],
        normal_speed_repeat_count=_NORMAL_SPEED_REPEATS[r],
        earlier_words_recalls=_EARLIER_WORDS_RECALLS[r],
        min_lines=lines_for(min_minutes),
        max_lines=lines_for(max_minutes),
        min_minutes=min_minutes,
        max_minutes=max_minutes,
    )


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

"""
Tuning a learner's next lessons from what they said about the earlier ones.

After a lesson the learner can say, for each of three aspects, that it should
go one way, the other way, or stay as it was (AudioLessonFeedback). Each aspect
is a level from -2 to +2, starting at 0 (the lesson as it was before tuning
existed). Walking through the learner's lessons from the oldest, every answer
moves the level one step, and the level stays within -2..+2 at every step: so
after "faster" three times, one "slower" already slows the next lesson down.
"Just right" leaves the level where it is.

The levels fill in the numbers of the A0 lesson prompt (prompt_values). Above
A0, pace and repetition are applied by code to the lessons written with markers
(shared_lesson_values): a shared lesson is said again at the learner's pace
for them. Lessons without markers (meaning lessons) are not tuned. Length is
for A0 lessons only.

Length is not a level but the learner's setting, in minutes
(UserPreference.AUDIO_LESSON_MINUTES), which they see and can set themselves:
"too short" and "too long" move it one step (lesson_minutes_after). The prompt
asks for a lesson between that length and a few minutes more, and fills it
with rehearsal of the learner's earlier dialogues when the new words alone are
done sooner: a lesson that came out shorter than asked made one learner miss
their 10-minute daily goal (20 Nov 2026).
"""

from dataclasses import asdict, dataclass, replace

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
    """The learner's tuning. Its pace is their time to answer when they have
    one (UserPreference.AUDIO_LESSON_ANSWER_TIME); before that setting
    existed, it came from their pace answers alone, which is what it still
    is for a learner who never gave one."""
    from zeeguu.core.model.user_preference import UserPreference

    tuning = tuning_from(AudioLessonFeedback.history(user, language.id))
    chosen = UserPreference.get_audio_lesson_answer_time(user)
    if chosen is not None:
        tuning = replace(tuning, pace=-chosen)
    # Repetition likewise (UserPreference.AUDIO_LESSON_REPETITION)
    chosen = UserPreference.get_audio_lesson_repetition(user)
    if chosen is not None:
        tuning = replace(tuning, repetition=-chosen)
    return tuning


# The time to answer the learner can choose: minus the pace level, so that
# more is more time ("Too fast" moves it up a step). 0 is the default.
ANSWER_TIME_CHOICES = (-2, -1, 0, 1, 2)


def answer_time_for(user, language) -> int:
    """The time to answer the next lessons are said with, as set or as tuned."""
    return -tuning_for(user, language).pace


def answer_time_after(pace, value) -> int:
    """The time to answer after a pace answer on a lesson said at `pace`:
    a step from that lesson's, within the choices."""
    moved = max(LEVELS[0], min(LEVELS[-1], pace + ASPECTS["pace"].get(value, 0)))
    return -moved


# The repetition the learner can choose: minus the repetition level, so that
# more is more repetition. Above A0 only three steps differ (each answer said
# once, twice, three times), so the setting stays within them there.
REPETITION_CHOICES = (-2, -1, 0, 1, 2)
ABOVE_A0_REPETITION_CHOICES = (-1, 0, 1)


def _within(level, a0):
    choices = REPETITION_CHOICES if a0 else ABOVE_A0_REPETITION_CHOICES
    return max(choices[0], min(choices[-1], level))


def repetition_for(user, language, a0=True) -> int:
    """The repetition the next lessons are said with, as set or as tuned."""
    return _within(-tuning_for(user, language).repetition, a0)


def repetition_after(repetition, value, a0=True) -> int:
    """The repetition after a repetition answer on a lesson said at
    `repetition` (the tuning level): a step from that lesson's."""
    moved = max(LEVELS[0], min(LEVELS[-1], repetition + ASPECTS["repetition"].get(value, 0)))
    return _within(-moved, a0)


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
# Above A0 the model writes the challenges, and the lesson is shared, so
# repetition is how often each answer is said after the time to answer. A0
# lessons keep saying it twice: their repetition is in the recalls.
_ANSWER_REPEATS = (3, 3, 2, 1, 1)
DEFAULT_ANSWER_REPEATS = 2
_TIMES = {1: "once", 2: "twice", 3: "three times"}
_EARLIER_WORDS_RECALLS = (
    "many times", "several times", "several times", "two or three times", "once",
)
# The length the learner can choose, in minutes, and the step "too short" and
# "too long" move it by.
# 25 at most: past that, a lesson runs out of earlier dialogues to rehearse
# (a learner with 14 earlier lessons reaches ~24 minutes; eval
# zeeguu-experiments audio-lessons/2026-11-20-a0-length-rehearsal).
LESSON_MINUTES_CHOICES = (5, 10, 15, 20, 25)
LESSON_MINUTES_STEP = 5
# How much longer than the chosen length a lesson may run; never past the
# longest choice, which is a hard cap: a 25-minute lesson is asked for 22-25.
_LESSON_MINUTES_MARGIN = 3
MAX_LESSON_MINUTES = LESSON_MINUTES_CHOICES[-1]

# 63 A0 lessons in prod (20 Nov 2026): 4.9-6.8 seconds per voice line,
# median 5.5. The earlier estimate, 200 lines in 12 minutes, was 3.6.
SECONDS_PER_LINE = 5.5


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
    return round(minutes * 60 / SECONDS_PER_LINE)


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
        answer_repeats=DEFAULT_ANSWER_REPEATS,
        earlier_words_recalls=_EARLIER_WORDS_RECALLS[r],
        min_lines=lines_for(min_minutes),
        max_lines=lines_for(max_minutes),
        min_minutes=min_minutes,
        max_minutes=max_minutes,
    )


def shared_lesson_values(tuning: LessonTuning = None) -> dict:
    """
    The numbers a marked lesson above A0 is expanded with (lesson_script):
    pace, 5-10 s to answer at the default pace (time_to_answer.ABOVE_A0_SECONDS;
    7-14 s at the slowest, 3-6 s at the fastest), and how often
    each answer is said. Without a tuning, the default:
    what the shared lesson is stored and voiced with. With the learner's, what
    their own copy of its audio is said with (DailyAudioLesson.dialogue_tuning).
    """
    tuning = tuning or LessonTuning()
    values = prompt_values(tuning, DEFAULT_LESSON_MINUTES)
    from zeeguu.core.audio_lessons.lesson_script.time_to_answer import ABOVE_A0_SECONDS, DEFAULT_ANSWER_PAUSE

    values["answer_repeats"] = _ANSWER_REPEATS[tuning.repetition + 2]
    # The bounds move with the pace: "much more" time would otherwise give a
    # long answer nothing more than the default's 10 s.
    scale = values["answer_pause"] / DEFAULT_ANSWER_PAUSE
    values["answer_seconds"] = tuple(round(bound * scale) for bound in ABOVE_A0_SECONDS)
    return values


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


# What each step of the two settings means for the learner, in seconds and
# times, at their level: the one place these words are made, for the settings
# page and for what the feedback box says after an answer.

# The answers the time to answer is shown for: one word, and a long answer of
# the level (A0 answers run to about four words; above, to about twelve).
_SHORTEST_ANSWER = "Tak"
_LONGEST_ANSWER = {True: "en to tre fire", False: "en to tre fire fem seks syv otte ni ti elleve tolv"}


def _values(a0, tuning):
    return prompt_values(tuning, DEFAULT_LESSON_MINUTES) if a0 else shared_lesson_values(tuning)


def answer_time_label(level, a0) -> str:
    from zeeguu.core.audio_lessons.lesson_script.time_to_answer import time_to_answer

    values = _values(a0, LessonTuning(pace=-level))
    short, long = time_to_answer(_SHORTEST_ANSWER, values), time_to_answer(_LONGEST_ANSWER[a0], values)
    return f"{short}–{long} seconds"


def repetition_label(level, a0) -> str:
    values = _values(a0, LessonTuning(repetition=-level))
    if a0:
        return f"each new word comes back {values['recalls_to_say']} times"
    return f"each answer said {_TIMES[values['answer_repeats']]}"


def setting_choices(a0) -> dict:
    """{setting: [{value, label}]}, the steps in order, as strings like the
    preferences: what the settings page offers."""
    repetition = REPETITION_CHOICES if a0 else ABOVE_A0_REPETITION_CHOICES
    return {
        "answer_time": [{"value": str(l), "label": answer_time_label(l, a0)} for l in ANSWER_TIME_CHOICES],
        "repetition": [{"value": str(l), "label": repetition_label(l, a0)} for l in repetition],
    }


def next_lesson_summary(user, language, a0) -> str:
    """What the next lessons will be like, said in seconds and times:
    "5–10 seconds to answer, each answer said twice"."""
    return (
        f"{answer_time_label(answer_time_for(user, language), a0)} to answer, "
        f"{repetition_label(repetition_for(user, language, a0), a0)}"
    )

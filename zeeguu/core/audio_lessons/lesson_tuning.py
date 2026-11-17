"""
Tuning a learner's next dialogue lessons from what they said about the earlier ones.

After a lesson the learner can say, for each of three aspects, that it should
go one way, the other way, or stay as it was (AudioLessonFeedback). Each aspect
is a level from -2 to +2, starting at 0 (the lesson as it was before tuning
existed). Walking through the learner's lessons from the oldest, every answer
moves the level one step, and the level stays within -2..+2 at every step: so
after "faster" three times, one "slower" already slows the next lesson down.
"Just right" leaves the level where it is.

The levels fill in the numbers of the lesson prompt: the A0 prompt
(prompt_values) and, from A1 up, the topic and situation prompts
(dialogue_prompt_values). The two kinds of lesson are tuned apart: an A0
lesson is built on drilling, so "less repetition" there says nothing about an
A1 lesson. Word lessons (auto mode) are not tuned: each is one word's lesson,
shared by every learner of that word.
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


def tuning_for(user, language, builds_on_history=True) -> LessonTuning:
    """From the learner's answers on the lessons of the same kind: A0 lessons
    (builds_on_history) or the dialogue lessons of the other levels."""
    return tuning_from(AudioLessonFeedback.history(user, language.id, builds_on_history))


def is_untuned(tuning) -> bool:
    return tuning is None or tuning == LessonTuning()


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
# length (+ is shorter): the lesson's longest length, in lines. The prompt says
# the length follows from the content, so with a lot of repetition in a short
# lesson the model fits fewer recalls in, rather than running over.
_MAX_LINES = (250, 225, 200, 160, 120)

# 200 lines measured about 12 minutes.
_SECONDS_PER_LINE = 12 * 60 / 200


def prompt_values(tuning: LessonTuning) -> dict:
    p, r, n = tuning.pace + 2, tuning.repetition + 2, tuning.length + 2
    max_lines = _MAX_LINES[n]
    return dict(
        answer_pause=_ANSWER_PAUSE[p],
        repeat_pause=_REPEAT_PAUSE[p],
        recalls_to_say=_RECALLS_TO_SAY[r],
        recalls_to_understand=_RECALLS_TO_UNDERSTAND[r],
        normal_speed_repeats=_TIMES[_NORMAL_SPEED_REPEATS[r]],
        normal_speed_repeat_count=_NORMAL_SPEED_REPEATS[r],
        earlier_words_recalls=_EARLIER_WORDS_RECALLS[r],
        max_lines=max_lines,
        max_minutes=round(max_lines * _SECONDS_PER_LINE / 60),
    )


# The topic and situation prompts, from A1 up. Level 0 is the prompt as it was
# (v2), so a learner who never answered gets the same lesson, and the dialogue
# can still be shared with other learners.
# pace: as at A0, the pause for the learner to answer a challenge, and between
# repetitions of the answer.
# repetition (+ is less): how many times the answer is said after a challenge;
# how many earlier challenges are asked again at the end; and, at the far end,
# no phrase asked for twice.
_ANSWER_TIMES = (3, 2, 2, 1, 1)
_REVIEW_CHALLENGES = (6, 4, 0, 0, 0)
_NO_PHRASE_TWICE = (False, False, False, False, True)
# length (+ is shorter): the dialogue's lines, the challenges on it, and the
# challenges beyond it.
_DIALOGUE_LINES = ("about 24", "about 20", "at least 14", "about 11", "about 8")
_CHALLENGES = ("about 14", "about 11", "at least 8", "about 6", "about 4")
_EXTRA_CHALLENGES = (6, 5, 4, 3, 2)


def _answer_lines(times, repeat_pause):
    lines = [f"    Man: <target language phrase> [{repeat_pause} seconds]"]
    lines += [f"    Man: <repeat same phrase> [{repeat_pause} seconds]"] * (times - 1)
    return "\n".join(lines) + "\n"


def dialogue_prompt_values(tuning: LessonTuning) -> dict:
    """The numbers of dialogue_lesson--{situation,topic}-v3.txt."""
    p, r, n = tuning.pace + 2, tuning.repetition + 2, tuning.length + 2
    times, review = _ANSWER_TIMES[r], _REVIEW_CHALLENGES[r]
    repeat_rule = ""
    if times == 1:
        repeat_rule += " The phrase is said once after each challenge, not repeated."
    if _NO_PHRASE_TWICE[r]:
        repeat_rule += " Never ask for the same phrase twice: every challenge practises something new."
    review_section = ""
    if review:
        review_section = (
            "\n    Finally, add a short introduction IN {source_language} (similar to \"Let's go\n"
            f"    over some of these again\" but in {{source_language}}), and ask {review} of the\n"
            "    earlier challenges again, in a different order, answered as before.\n"
        )
    return dict(
        answer_pause=_ANSWER_PAUSE[p],
        repeat_pause=_REPEAT_PAUSE[p],
        answer_lines=_answer_lines(times, _REPEAT_PAUSE[p]),
        repeat_rule=repeat_rule,
        review_section=review_section,
        dialogue_lines=_DIALOGUE_LINES[n],
        challenges=_CHALLENGES[n],
        extra_challenges=_EXTRA_CHALLENGES[n],
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

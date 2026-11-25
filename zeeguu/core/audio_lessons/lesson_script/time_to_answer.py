"""
How long the silence after a prompt is: the time the learner gets to answer.

It grows with the answer: a beginner recalls each word and then says it
slowly, so every word adds time, on top of a short start. The learner's pace
scales all of it (the answer pause, 3-7 s, against its default of 5). At the
default pace: "Hej." 3 s, "Undskyld, hvad koster en billet?" 8 s. Before,
every answer had the same 5 s, and a learner asked for the time to follow the
answer's length (Nov 2026). Estimates, not measured: listen to lessons, or
time a few learners, before trusting them.
"""

import re

SECONDS_TO_START = 2
SECONDS_PER_WORD = 1.2
DEFAULT_ANSWER_PAUSE = 5
# 12 s at most: at the default pace no A0 answer in the evaluation needed
# more (8 words: 12 s); the slowest pace hit 15 s only for 4 answers of 293.
MIN_SECONDS, MAX_SECONDS = 2, 12
_ANSWER_WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")


def time_to_answer(answer, values):
    """Seconds of silence after a prompt whose answer is `answer`.
    values: lesson_tuning.prompt_values (the learner's pace)."""
    words = len(_ANSWER_WORD.findall(answer))
    pace = values["answer_pause"] / DEFAULT_ANSWER_PAUSE
    seconds = round(pace * (SECONDS_TO_START + SECONDS_PER_WORD * words))
    return max(MIN_SECONDS, min(MAX_SECONDS, seconds))

"""
Verifies that a generated audio-lesson script is actually in the language we asked
for.

LLMs occasionally ignore the "Teacher speaks X, Man/Woman speak Y" instruction and
emit the whole script in one language — most visibly, a "Danish" lesson where the
dialogue is in English. The script is expensive to turn into audio and lands
directly in a user's daily lesson, so we check it before synthesis rather than
after.

Only the target-language voices are checked. The Teacher's lines look checkable
but are bilingual by design: every challenge is a native-language lead-in followed
by the exact target sentence the listener must produce ("Скажіть, the news says it
will rain tomorrow"). Checked against production, that rule fired three times and
was wrong all three. Man/Woman/TeacherL2 lines carry no such ambiguity.

Each line is judged on its own — is this plausibly Danish? — and the lesson is
condemned only if enough of them are not. That two-level shape is what makes it
work on a script, where a line is four words long. Individual short lines are
unreliable even for a good detector: correct Danish "Er det i kantinen?" scores
0.12. Aggregating over the lines is what turns an unreliable signal into a
trustworthy one, and it replaced an earlier scheme that glued lines into
300-character chunks to reach a detector's minimum, then argued about what share
of chunks could be wrong.
"""

from zeeguu.core.audio_lessons.script_parser import parse_script
from zeeguu.core.language.language_check import (
    GROUP_LEVEL_FLOOR,
    LanguageMismatch,
    detected_language_of,
    plausibility,
)
from zeeguu.logging import log

# Voices that speak the language being learned. "Teacher" is deliberately absent —
# see the module docstring.
TARGET_LANGUAGE_VOICES = {"teacherl2", "man", "woman"}

TARGET_LABEL = "Man/Woman/TeacherL2"

# How much of a lesson may read as another language before the lesson is wrong.
#
# With the floor under the correct band, sound lessons sit near zero rather than
# near half, so this can come down far enough to catch the shape that was slipping
# through: a dialogue lesson whose conversation is English but whose practice
# answers are genuinely in the target language lands at 33-44%, because the practice
# section is not wrong. Dialogues 235 and 236 are that shape, and a 0.45 threshold
# missed both.
LESSON_LEVEL_THRESHOLD = 0.25

# Below this a line says nothing at all. It can stay small because the floor is set
# under the band that correct short text occupies, rather than above it — raising
# this to 9 words was the other way to fix the same problem, and it was worse: the
# Italian-written-in-Spanish lessons have no line longer than eight words, so it
# bought precision by discarding the evidence.
MIN_WORDS_PER_LINE = 3

# Lines are judged in groups of this many, not one at a time.
#
# One line is too little for lingua to discriminate with: correct short Danish
# scores 0.08-0.15 as Danish, wrong-language text scores 0.00-0.14, and those bands
# overlap, so no floor separates them one line at a time. The 0.05 floor that
# preceded this worked by letting almost everything through and relying on the
# aggregate — which means a script in a SIBLING of the target language was caught
# only when some of its lines happened to dip under, not because it was detected.
#
# Four lines together and the overlap is gone: measured on production scripts,
# sound groups score 0.66-0.97 and wrong ones 0.00-0.07. More text makes lingua more
# DISCRIMINATING, not merely more confident — a Danish paragraph is 4e-09 plausible
# Norwegian where a Danish line is 0.10 — which is what turns sibling substitution
# from luck into detection.
LINES_PER_GROUP = 4

# ...but absorbing requires something to absorb INTO. The threshold above is a
# share, and a share of two lines is not evidence: correct short Danish sits under
# the floor routinely ("Jeg bor i et hus." is 0.16, "Er det i kantinen?" is 0.12),
# so a lesson with a brief dialogue was condemned on two sound lines. The corpus
# that calibrated the threshold had 10-30 lines per lesson; below roughly this much
# judged text there is no cushion, and the honest answer is "can't judge".
MIN_CHARS_TO_JUDGE_A_LESSON = 200


def _without_echoes(lines: list) -> list:
    """
    Drop the drill echo: every practice phrase is spoken twice in a row.

    Grouping assumes each line adds text, and in the practice section that is
    false — four lines there are two phrases said twice. A group then carries half
    the evidence it looks like it carries, which is exactly how grouping alone
    flagged sixty sound lessons: "Har du en pen? Har du en pen?" is not four lines
    of Danish, it is four words.

    A dialogue never repeats a line back to back, so removing consecutive
    duplicates costs the conversation nothing and makes a group of four mean four.
    """
    kept = []
    for line in lines:
        if kept and line.strip().lower() == kept[-1].strip().lower():
            continue
        kept.append(line)
    return kept


def _reads_as(line, target_language) -> str:
    detected = detected_language_of(line)
    return detected if detected != target_language else "no language confidently"


def find_language_mismatches(
    script: str, target_language: str, source_language=None, label_for_log: str = ""
) -> list:
    """
    Check a lesson script against the language it was supposed to be written in.

    Args:
        script: the raw script, with "Teacher:" / "Man:" / ... voice labels
        target_language: Zeeguu code of the language being learned
        source_language: accepted and ignored — the teacher's lines are bilingual
            by design and can't be judged. Kept so call sites read symmetrically.

    Returns:
        A list of LanguageMismatch — empty when the script looks right, and also
        empty when there was too little to judge or the language has no model.
    """
    lines = [
        text
        for voice_type, text, _ in parse_script(script)
        if voice_type in TARGET_LANGUAGE_VOICES
    ]

    long_enough = _without_echoes(
        [line for line in lines if len(line.split()) >= MIN_WORDS_PER_LINE]
    )
    groups = [
        " ".join(long_enough[i : i + LINES_PER_GROUP])
        for i in range(0, len(long_enough), LINES_PER_GROUP)
    ]

    judged = 0
    judged_chars = 0
    implausible = []
    for group in groups:
        confidence = plausibility(group, target_language)
        if confidence is None:
            continue
        judged += 1
        judged_chars += len(group)
        if confidence < GROUP_LEVEL_FLOOR:
            implausible.append((group, confidence))

    if not judged or judged_chars < MIN_CHARS_TO_JUDGE_A_LESSON:
        # Named, because a skip and a pass look identical in the audit output
        # otherwise — and a lesson that was never judged is not a lesson that was
        # found sound.
        log(
            f"[script_language_validator] {label_for_log or 'script'}: too little "
            f"{target_language} text to judge ({judged} groups, {judged_chars} chars)"
        )
        return []

    share = len(implausible) / judged
    if share <= LESSON_LEVEL_THRESHOLD:
        return []

    worst_line, worst_confidence = min(implausible, key=lambda pair: pair[1])
    return [
        LanguageMismatch(
            label=f"{TARGET_LABEL} ({len(implausible)} of {judged} groups)",
            expected=target_language,
            # What it reads as instead, taken from the worst line — the plausibility
            # question does not produce this, but a reader and a retry prompt both
            # want to know.
            # Only meaningful when the winner differs from what we asked for. A line
            # can be implausible while still reading as the expected language —
            # confidence split across siblings — and reporting "expected da but
            # reads as da" is nonsense.
            detected=_reads_as(worst_line, target_language),
            expected_probability=worst_confidence,
            sample=worst_line[:120],
        )
    ]

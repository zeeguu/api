"""
Verifies that a generated audio-lesson script is actually in the languages we
asked for.

LLMs occasionally ignore the "Teacher speaks X, Man/Woman speak Y" instruction and
emit the whole script in one language — most visibly, a "Danish" lesson where the
dialogue is in English. The script is expensive to turn into audio and lands directly
in a user's daily lesson, so we check it before synthesis rather than after.

The detection itself lives in ``zeeguu.core.language.language_check``, which every
LLM call site that must produce a foreign language shares. What is specific to a
lesson script — and all that's left here — is knowing which voice speaks which
language.

Only the target-language voices are checked. The Teacher's lines look checkable
but are bilingual by design: every challenge is a native-language lead-in
followed by the exact target sentence the listener must produce
("Скажіть, the news says it will rain tomorrow"). When the learned language is
the more prominent of the two — an English course with a Ukrainian-speaking
teacher — the target sentences outweigh the lead-ins and the teacher's lines read
as the target language. Checked against production, that rule fired three times
and was wrong all three; it would have blocked lesson generation for every
English learner with a non-English native language. The failure it was meant to
catch (a teacher lecturing entirely in the language being taught) has never been
observed. Man/Woman/TeacherL2 lines carry no such ambiguity — they are pure
target language — and they caught every real failure we have.
"""

from zeeguu.core.audio_lessons.script_parser import parse_script
from zeeguu.core.language.language_check import passage_mismatch

# Voices that speak the language being learned. "Teacher" is deliberately absent —
# see the module docstring.
TARGET_LANGUAGE_VOICES = {"teacherl2", "man", "woman"}

TARGET_LABEL = "Man/Woman/TeacherL2"


def find_language_mismatches(script: str, target_language: str, source_language=None) -> list:
    """
    Check a lesson script against the language it was supposed to be written in.

    Args:
        script: the raw script, with "Teacher:" / "Man:" / ... voice labels
        target_language: Zeeguu code of the language being learned
        source_language: accepted and ignored — the teacher's lines are bilingual
            by design and can't be judged. Kept so call sites read symmetrically.

    Returns:
        A list of LanguageMismatch — empty when the script looks right, and also
        empty when the script was too short or the language has no detector.
    """
    target_texts = [
        text
        for voice_type, text, _ in parse_script(script)
        if voice_type in TARGET_LANGUAGE_VOICES
    ]

    # Checked as a passage, not as one blob: scripts fail in halves. The lesson that
    # started all this had an all-English opening dialogue followed by correct Danish
    # practice phrases — 71% Danish overall, which a whole-text check waves through.
    mismatch = passage_mismatch(target_texts, target_language, TARGET_LABEL)
    return [mismatch] if mismatch else []

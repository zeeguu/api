"""
Parsing of audio-lesson scripts into voice segments.

Kept separate from voice_synthesizer so that consumers which only need to read a
script (e.g. the language validator) don't pull in Google TTS and pydub.
"""

import re
from typing import List, Tuple

from zeeguu.core.audio_lessons.voice_config import DEFAULT_SILENCE_SECONDS

VOICE_LABELS = ("Teacher", "TeacherL2", "Man", "Woman")

_VOICE_LABEL_PATTERN = re.compile(
    r"^(" + "|".join(VOICE_LABELS) + r"):\s*", re.IGNORECASE
)
_VOICE_LINE_PATTERN = re.compile(
    r"^(" + "|".join(VOICE_LABELS) + r"):\s*(.+)$", re.IGNORECASE
)
# [slow], and the variants a model writes for it ([slowly], [slow speed]): any
# of them left in the text would be read aloud.
_SLOW_MARKER = re.compile(r"\s*\[slow[a-z ]*\]", re.IGNORECASE)

# A label in markdown emphasis, "**Woman:**", "**Woman**:", "*Mads:*", as
# models sometimes write it.
_STARRED_LABEL = re.compile(r"^\*+\s*([^*:\s][^*:]{0,29}?)\s*(?::\s*\*+|\*+\s*:)")


def _unbold_label(line: str) -> str:
    """
    '**Woman:** Hej' -> 'Woman: Hej'. Before this, such a line was not a voice
    line: it was joined to the line before and read out, stars and all, by
    whoever spoke that line.
    """
    return _STARRED_LABEL.sub(r"\1:", line)


def join_continuation_lines(script: str) -> str:
    """
    Join continuation lines back to their parent voice line.

    Sometimes the LLM breaks a single voice instruction across multiple lines,
    e.g.:
        Teacher: In the following conversation...
        Throughout the dialogue, you will hear the word [0.2 seconds]

    This joins such continuation lines back to the previous voice line.
    """
    joined_lines = []

    for line in script.split("\n"):
        stripped = _unbold_label(line.strip())
        if not stripped:
            continue

        if _VOICE_LABEL_PATTERN.match(stripped):
            joined_lines.append(stripped)
        elif _SLOW_MARKER.fullmatch(stripped):
            # A [slow] on a line of its own belongs to no line: appended to the
            # previous one, it would slow down whoever spoke last.
            continue
        elif stripped.startswith("[") and re.search(
            r"\[([0-9.]+)\s*seconds?", stripped, re.IGNORECASE
        ):
            # Standalone timing/silence marker. A [slow] beside it belongs to no
            # line either, as above.
            joined_lines.append(_SLOW_MARKER.sub("", stripped).strip())
        elif joined_lines:
            # Continuation line - append to previous line
            joined_lines[-1] = joined_lines[-1] + " " + stripped
        # else: orphan line before any voice line - skip it

    return "\n".join(joined_lines)


# A line that reads like a speaker's: a short label, a colon, then text.
# "Mads: Hej Sofie!" and "Man 1: Hej!" match. A colon between two digits is a
# time, not a label: a wrapped line like "klokken 10:30" is spoken as it is.
_SPEAKER_LIKE_LINE = re.compile(r"^([^\s:\[\]*][^:\[\]*]{0,29}?)\s*:(?!\d)\s*\S")


def unknown_speaker_labels(script: str) -> List[str]:
    """
    The labels of lines that read like a speaker's line but name no voice we have.

    Since 16 Nov 2026 the model sometimes labels dialogue lines with the
    characters' names ("Mads: Hej Sofie!") instead of Man:/Woman:. parse_script
    finds no voice on such lines, so the whole dialogue went unsaid and the
    learner heard only the challenges (dialogue 525, lesson 1396).

    Before the first voice line a model may write a title or a header
    ("Holidays: Beach or Mountains?", "Topic: Ordering coffee"), which
    parse_script skips. There, a label counts only when it labels more than
    one line in the script, as a dialogue's speakers do.
    """
    lines = [_unbold_label(l.strip()) for l in script.split("\n") if l.strip()]
    found = []  # (label, before the first voice line)
    seen_a_voice = False
    for stripped in lines:
        if _VOICE_LABEL_PATTERN.match(stripped):
            seen_a_voice = True
            continue
        match = _SPEAKER_LIKE_LINE.match(stripped)
        if match:
            found.append((match.group(1), not seen_a_voice))

    counts = {}
    for label, _ in found:
        counts[label] = counts.get(label, 0) + 1
    labels = []
    for label, before_any_voice in found:
        if before_any_voice and counts[label] < 2:
            continue
        if label not in labels:
            labels.append(label)
    return labels


def parse_script(script: str, with_speed: bool = False) -> List[Tuple]:
    """
    Parse the script into individual voice segments.

    A line may carry a [slow] marker: say it slower than the rest of the lesson
    (A0 lessons say each new word slowly once, so a beginner can hear its sounds).
    The marker is always stripped from the text.

    Returns:
        List of tuples: (voice_type, text, silence_after), or, with_speed,
        (voice_type, text, silence_after, slow)
    """
    # First, join any continuation lines back to their parent
    script = join_continuation_lines(script)

    segments = []

    for line in script.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Handle standalone silence/timing markers like [1 seconds], [1 second silence]
        if line.startswith("["):
            duration_match = re.search(
                r"\[([0-9.]+)\s*seconds?\s*(?:silence)?\]", line, re.IGNORECASE
            )
            if duration_match:
                duration = float(duration_match.group(1))
                segments.append(("silence", "", duration, False) if with_speed else ("silence", "", duration))
            continue

        # Parse voice lines like "Teacher: Some text [2 seconds]"
        voice_match = _VOICE_LINE_PATTERN.match(line)
        if not voice_match:
            continue

        voice_type = voice_match.group(1).lower()
        text = voice_match.group(2)

        # Extract silence duration from the last [X seconds] marker
        silence_duration = DEFAULT_SILENCE_SECONDS
        silence_match = re.search(r"\[([0-9.]+)\s*seconds?\]", text)
        if silence_match:
            silence_duration = float(silence_match.group(1))
        # Strip ALL timing annotations from the text
        text = re.sub(r"\s*\[([0-9.]+)\s*seconds?\s*(?:silence)?\]", "", text)
        slow = bool(_SLOW_MARKER.search(text))
        text = _SLOW_MARKER.sub("", text).strip()

        if with_speed:
            segments.append((voice_type, text, silence_duration, slow))
        else:
            segments.append((voice_type, text, silence_duration))

    return segments

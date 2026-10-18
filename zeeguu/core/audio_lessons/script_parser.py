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
        stripped = line.strip()
        if not stripped:
            continue

        if _VOICE_LABEL_PATTERN.match(stripped):
            joined_lines.append(stripped)
        elif stripped.startswith("[") and re.search(
            r"\[([0-9.]+)\s*seconds?", stripped, re.IGNORECASE
        ):
            # Standalone timing/silence marker
            joined_lines.append(stripped)
        elif joined_lines:
            # Continuation line - append to previous line
            joined_lines[-1] = joined_lines[-1] + " " + stripped
        # else: orphan line before any voice line - skip it

    return "\n".join(joined_lines)


_SLOW_MARKER = re.compile(r"\s*\[slow\]", re.IGNORECASE)


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

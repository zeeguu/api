"""
Parsing of audio-lesson scripts into voice segments.

Kept separate from voice_synthesizer so that consumers which only need to read a
script (e.g. the language validator) don't pull in Google TTS and pydub.
"""

import re
from dataclasses import dataclass
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
# The markers of an A0 script before it is expanded (lesson_script). Only
# there: the language check reads the marked script, and must not read the
# markers as words.
_LESSON_MARKER = re.compile(r"\s*\[(?:drill|answer|understand)\]", re.IGNORECASE)

# A label in bold, "**Woman:**" or "**Woman**:", as models sometimes write it.
_BOLD_LABEL = re.compile(r"^\*\*\s*([^*:\s][^*:]{0,29}?)\s*(?::\s*\*\*|\*\*\s*:)")


def _unbold_label(line: str) -> str:
    """'**Woman:** Hej' -> 'Woman: Hej'. Before this, such a line was dropped."""
    return _BOLD_LABEL.sub(r"\1:", line)


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
# "Mads: Hej Sofie!" matches. A label with a digit is not a speaker: a wrapped
# line like "klokken 10:30" is a continuation, and is spoken.
_SPEAKER_LIKE_LINE = re.compile(r"^([^\s:\[\]*0-9][^:\[\]*0-9]{0,29}?)\s*:\s*\S")


def unknown_speaker_labels(script: str) -> List[str]:
    """
    The labels of lines that read like a speaker's line but name no voice we have.

    Since 16 Nov 2026 the model sometimes labels dialogue lines with the
    characters' names ("Mads: Hej Sofie!") instead of Man:/Woman:. parse_script
    finds no voice on such lines, so the whole dialogue went unsaid and the
    learner heard only the challenges (dialogue 525, lesson 1396).

    The first line is not looked at when it is not a voice line: a dialogue
    lesson's title is there ("Holidays: Beach or Mountains?").
    """
    labels = []
    lines = [_unbold_label(l.strip()) for l in script.split("\n") if l.strip()]
    if lines and not _VOICE_LABEL_PATTERN.match(lines[0]):
        lines = lines[1:]
    for stripped in lines:
        if _VOICE_LABEL_PATTERN.match(stripped):
            continue
        match = _SPEAKER_LIKE_LINE.match(stripped)
        if match and match.group(1) not in labels:
            labels.append(match.group(1))
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
        text = _SLOW_MARKER.sub("", text)
        text = _LESSON_MARKER.sub("", text).strip()
        if with_speed:
            segments.append((voice_type, text, silence_duration, slow))
        else:
            segments.append((voice_type, text, silence_duration))

    return segments



@dataclass(frozen=True)
class DialogueLine:
    speaker: str  # "Man" or "Woman"
    text: str


def dialogue_lines(script: str) -> List[DialogueLine]:
    """
    The dialogue of a dialogue lesson, line by line.

    Every dialogue prompt has the Teacher set the scene and then play the whole
    dialogue in one go, before any drill: the dialogue is the first run of Man
    and Woman lines, silences not counting as a break. A run must have both
    speakers: a challenge's answer is a run of one speaker saying a phrase twice
    ("Man: Regningen, tak." / "Man: Regningen, tak."). A run of a single line is
    skipped too: in one A0 script of 568 (checked 26 Nov 2026) the model started
    the dialogue, had the Teacher interrupt it, and then played the real one.

    Returns [] for a script with no such run, and for one whose dialogue is
    labeled with the characters' names (see unknown_speaker_labels): its Man
    and Woman lines are all drills. Only labels before the first Man or Woman
    line count: one later ("Remember: say tak.", a wrapped Teacher line) is
    not the dialogue.
    """
    if unknown_speaker_labels(_before_first_man_or_woman_line(script)):
        return []
    run = []
    for voice, text, _ in parse_script(script):
        if voice in ("man", "woman") and text.strip():
            run.append(DialogueLine(voice.capitalize(), text.strip()))
        elif voice in ("man", "woman", "silence"):
            # A line left empty once its markers are stripped ("Man: [2 seconds]")
            # says nothing: like a silence, not a break in the dialogue.
            continue
        elif _is_dialogue(run):
            return run
        else:
            run = []
    return run if _is_dialogue(run) else []


def _is_dialogue(run):
    return len(run) >= 2 and {"Man", "Woman"} <= {line.speaker for line in run}


def _before_first_man_or_woman_line(script):
    lines = script.split("\n")
    for i, line in enumerate(lines):
        voice = _VOICE_LABEL_PATTERN.match(_unbold_label(line.strip()))
        if voice and voice.group(1).lower() in ("man", "woman"):
            return "\n".join(lines[:i])
    return script

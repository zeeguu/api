"""
The marked script, as the model wrote it (roles already relabeled as voices),
into the expanded script that is stored and synthesized: every repetition and
every pause added here, from the learner's tuning.
"""

import re
from dataclasses import replace

from zeeguu.core.audio_lessons.lesson_script.markers import DIALOGUE_MARKER, LINE_MARKER, VOICE_LINE
from zeeguu.core.audio_lessons.lesson_script.spoken_line import SpokenLine, spoken_lines, without_chevrons
from zeeguu.core.audio_lessons.lesson_script.time_to_answer import time_to_answer
from zeeguu.core.audio_lessons.lesson_script.voices import TEACHER

_PAUSE = re.compile(r"\s*\[([0-9.]+)\s*seconds?\]", re.IGNORECASE)
# A voice label as the model sometimes writes it: in bold ("**Teacher:**",
# "**Teacher**:"), or in another case ("TEACHER:").
_LOOSE_LABEL = re.compile(
    r"^\**\s*(teacherl2|teacher|man|woman)\s*(?::\s*\**|\**\s*:)\s*", re.IGNORECASE
)
_LABELS = {"teacher": "Teacher", "teacherl2": "TeacherL2", "man": "Man", "woman": "Woman"}
_ANY_MARKER = re.compile(r"\[([a-z][a-z ]*\d*)\]", re.IGNORECASE)
_KNOWN_INLINE = ("slow",)
# What the model writes when it means "no marker": twice in the eval it wrote
# one, echoing the prompt's wording ("[no marker]", "[plain]"). A plain line.
_PLAIN = re.compile(r"\s*\[(?:plain|no marker|none)\]\s*$", re.IGNORECASE)


class MarkupError(ValueError):
    """The script uses a marker wrongly; the message says how, for a rewrite."""


def clean_script(script):
    """
    The marked script with its voice labels as expand() and challenges()
    read them: a bold or upper-case label written plainly ("**Teacher:**" ->
    "Teacher:"), and a line the model wrapped joined back to the voice line it
    continues. Only text before the first voice line, or after a blank line,
    is no one's line.
    """
    out = []
    for raw in (script or "").split("\n"):
        line = raw.strip()
        label = _LOOSE_LABEL.match(line)
        if label:
            line = f"{_LABELS[label.group(1).lower()]}: {line[label.end():]}"
        continues = (
            line and not label and not line.startswith("[")
            and out and VOICE_LINE.match(out[-1])
        )
        if continues:
            out[-1] = f"{out[-1]} {line}"
        else:
            out.append(line)
    return "\n".join(out)


def expand(script, values, dialogue, learner):
    """
    The full script from a marked one, its lines already labeled with voices.
    Built as SpokenLines (and blank lines as they are), written out as text
    at the end.

    values: lesson_tuning.prompt_values; dialogue: this lesson's dialogue as
    [(voice, text)]; learner: the learner's voice, "man" or "woman".
    Raises MarkupError on a marker it cannot expand.
    """
    out = []
    problems = []
    for raw in clean_script(script).split("\n"):
        line = raw.strip()
        if not line:
            out.append("")
            continue

        if DIALOGUE_MARKER.match(line):
            out += [SpokenLine(voice, text, 1) for voice, text in dialogue]
            continue

        if line.startswith("["):
            # Only [dialogue] stands on a line of its own (handled above), and
            # the model writes no pauses. Anything else would be skipped
            # silently by the parser: a [drill] on its own line, say, would
            # leave its word undrilled.
            problems.append(f"{line!r}: not a marker that stands on its own line")
            continue

        voice_line = VOICE_LINE.match(line)
        if not voice_line:
            # Text that is no one's line ("Here is your lesson:"): nobody would
            # say it, so it is not kept. Not a wrapped line (clean_script joined
            # those) and not the title (taken off before expanding).
            continue

        voice, text = voice_line.groups()
        voice = voice.lower()
        # Timing is code's: a pause the model wrote anyway is dropped, first,
        # so a marker before it ("[drill] [2 seconds]") is still at the end.
        text = _PAUSE.sub("", text).strip()
        text = _PLAIN.sub("", text)
        marker = LINE_MARKER.search(text)
        kind = marker.group(1).lower() if marker else None
        text = LINE_MARKER.sub("", text).strip()

        unknown = [
            m for m in _ANY_MARKER.findall(text)
            if m.lower() not in _KNOWN_INLINE and not re.match(r"^[0-9.]+\s*seconds?$", m)
        ]
        if unknown:
            problems.append(f"{line!r}: unknown marker [{unknown[0]}]")
            continue
        text = re.sub(r"\s*\[slow\]", "", text, flags=re.IGNORECASE)
        if voice != TEACHER:
            text = without_chevrons(text)

        if kind == "drill":
            out.append(SpokenLine(voice, text, values["repeat_pause"], slow=True))
            out += [SpokenLine(voice, text, values["repeat_pause"])] * values["normal_speed_repeat_count"]
        elif kind == "answer":
            # The line right before the answer is its prompt: a Teacher
            # question, or the Other person's line in an exchange. It gets the
            # time to answer. Not the learner's own line before it (two
            # answers in a row): that one already has its pause.
            prompt = next((i for i in range(len(out) - 1, -1, -1) if out[i]), None)
            if prompt is not None and isinstance(out[prompt], SpokenLine) and out[prompt].voice != learner:
                out[prompt] = replace(out[prompt], pause=time_to_answer(text, values))
            out += [SpokenLine(voice, text, values["repeat_pause"])] * 2
        elif kind == "understand":
            out.append(SpokenLine(voice, text, 1, slow=True))
            out.append(SpokenLine(voice, text, 1))
        else:
            out += spoken_lines(voice, text, 1)

    if problems:
        raise MarkupError("; ".join(problems))
    return "\n".join(str(line) for line in out).strip() + "\n"

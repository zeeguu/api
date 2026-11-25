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

_PAUSE = re.compile(r"\s*\[([0-9.]+)\s*seconds?\]\s*$", re.IGNORECASE)
_ANY_MARKER = re.compile(r"\[([a-z][a-z ]*\d*)\]", re.IGNORECASE)
_KNOWN_INLINE = ("slow",)
# What the model writes when it means "no marker": twice in the eval it wrote
# one, echoing the prompt's wording ("[no marker]", "[plain]"). A plain line.
_PLAIN = re.compile(r"\s*\[(?:plain|no marker|none)\]\s*$", re.IGNORECASE)


class MarkupError(ValueError):
    """The script uses a marker wrongly; the message says how, for a rewrite."""


def expand(script, values, dialogue, learner):
    """
    The full script from a marked one, its lines already labeled with voices.
    Built as SpokenLines (and the title and blank lines as they are), written
    out as text at the end.

    values: lesson_tuning.prompt_values; dialogue: this lesson's dialogue as
    [(voice, text)]; learner: the learner's voice, "man" or "woman".
    Raises MarkupError on a marker it cannot expand.
    """
    out = []
    problems = []
    for raw in script.split("\n"):
        line = raw.strip()
        if not line:
            out.append("")
            continue

        if DIALOGUE_MARKER.match(line):
            out += [SpokenLine(voice.capitalize(), text, 1) for voice, text in dialogue]
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
            # The title: kept as it is.
            out.append(line)
            continue

        voice, text = voice_line.groups()
        text = _PLAIN.sub("", text)
        marker = LINE_MARKER.search(text)
        kind = marker.group(1).lower() if marker else None
        text = LINE_MARKER.sub("", text)
        # Timing is code's: a pause the model wrote anyway is dropped.
        text = _PAUSE.sub("", text).strip()

        unknown = [
            m for m in _ANY_MARKER.findall(text)
            if m.lower() not in _KNOWN_INLINE and not re.match(r"^[0-9.]+\s*seconds?$", m)
        ]
        if unknown:
            problems.append(f"{line!r}: unknown marker [{unknown[0]}]")
            continue
        text = re.sub(r"\s*\[slow\]", "", text, flags=re.IGNORECASE)
        if voice != "Teacher":
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
            if prompt is not None and isinstance(out[prompt], SpokenLine) and out[prompt].voice != learner.capitalize():
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

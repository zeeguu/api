"""
A0 lesson scripts written with markers, expanded here into the full script.

The model writes each thing once and marks what kind of line it is; this code
adds the repetitions and every pause. So pace and repetition are exactly what
the learner's tuning says (lesson_tuning.prompt_values), rather than what the
model made of "about 5 recalls" and "[4 seconds]", and the model writes about
a quarter fewer lines. Design: docs future-work/a0-lesson-script-functions.md.

    Woman: Kaffe. [drill]                  slow once, then at normal speed
    Teacher: How do you say coffee? [ask]  then the time to answer
    Woman: En kaffe. [answer]              the answer, twice
    Man: Hvad skal det være? [understand]  slow once, then at normal speed
    [dialogue]                             this lesson's dialogue
    [respond 3]                            lesson 3's dialogue, answered: the other
                                           person's line, time to answer, the
                                           learner's line; then straight through

A line with no marker is said once, followed by one second (or by the pause
it carries, when it has one). The expanded script is what is stored and
synthesized: nothing downstream knows about markers.

top_up then makes a lesson shorter than the learner asked for long enough, by
adding [respond] rounds of earlier dialogues before the closing dialogue.
"""

import re

from zeeguu.core.audio_lessons.lesson_tuning import SECONDS_PER_LINE

VOICES = ("Teacher", "TeacherL2", "Man", "Woman")
LINE_MARKERS = ("drill", "ask", "answer", "understand")

_VOICE_LINE = re.compile(r"^(Teacher|TeacherL2|Man|Woman):\s*(.*)$")
_LINE_MARKER = re.compile(r"\s*\[(drill|ask|answer|understand)\]\s*$", re.IGNORECASE)
_PAUSE = re.compile(r"\s*\[([0-9.]+)\s*seconds?\]\s*$", re.IGNORECASE)
_DIALOGUE = re.compile(r"^\[dialogue\]$", re.IGNORECASE)
_RESPOND = re.compile(r"^\[respond\s+(\d+)\]$", re.IGNORECASE)
_ANY_MARKER = re.compile(r"\[([a-z][a-z ]*\d*)\]", re.IGNORECASE)
_KNOWN_INLINE = ("slow",)


class MarkupError(ValueError):
    """The script uses a marker wrongly; the message says how, for a rewrite."""


def _line(voice, text, pause):
    return f"{voice}: {text} [{_seconds(pause)} seconds]"


def _seconds(value):
    return int(value) if float(value).is_integer() else value


def respond_lines(dialogue, learner, values):
    """
    A dialogue for the learner to answer: each line of the other person, then
    the time to answer when the learner speaks next; each line of the learner,
    then the time to repeat it. Then the whole dialogue straight through.
    dialogue: [(voice, text)] with voice "man" / "woman"; learner: "man" / "woman".
    """
    out = []
    for i, (voice, text) in enumerate(dialogue):
        label = voice.capitalize()
        if voice == learner:
            out.append(_line(label, text, values["repeat_pause"]))
        else:
            learner_next = i + 1 < len(dialogue) and dialogue[i + 1][0] == learner
            out.append(_line(label, text, values["answer_pause"] if learner_next else 1))
    out.append("")
    out += [_line(voice.capitalize(), text, 1) for voice, text in dialogue]
    return out


def expand(script, values, dialogue, heard):
    """
    The full script from a marked one.

    values: lesson_tuning.prompt_values; dialogue: this lesson's dialogue as
    [(voice, text)]; heard: the earlier lessons (words_heard.HeardLesson),
    numbered from 1 as in the prompt's history table.
    Raises MarkupError on a marker it cannot expand.
    """
    out = []
    problems = []
    for raw in script.split("\n"):
        line = raw.strip()
        if not line:
            out.append("")
            continue

        if _DIALOGUE.match(line):
            out += [_line(voice.capitalize(), text, 1) for voice, text in dialogue]
            continue

        respond = _RESPOND.match(line)
        if respond:
            n = int(respond.group(1))
            if not 1 <= n <= len(heard):
                problems.append(f"[respond {n}]: there is no lesson {n}")
            elif not heard[n - 1].dialogue or not heard[n - 1].learner:
                problems.append(f"[respond {n}]: lesson {n} has no dialogue to rehearse")
            else:
                out += respond_lines(heard[n - 1].dialogue, heard[n - 1].learner, values)
            continue

        voice_line = _VOICE_LINE.match(line)
        if not voice_line:
            # The title, or a stray standalone pause: kept as it is.
            out.append(line)
            continue

        voice, text = voice_line.groups()
        marker = _LINE_MARKER.search(text)
        kind = marker.group(1).lower() if marker else None
        text = _LINE_MARKER.sub("", text)
        own_pause = _PAUSE.search(text)
        text = _PAUSE.sub("", text).strip()

        unknown = [
            m for m in _ANY_MARKER.findall(text)
            if m.lower() not in _KNOWN_INLINE and not re.match(r"^[0-9.]+\s*seconds?$", m)
        ]
        if unknown:
            problems.append(f"{line!r}: unknown marker [{unknown[0]}]")
            continue
        text = re.sub(r"\s*\[slow\]", "", text, flags=re.IGNORECASE)

        if kind == "drill":
            out.append(f"{voice}: {text} [slow] [{values['repeat_pause']} seconds]")
            out += [_line(voice, text, values["repeat_pause"])] * values["normal_speed_repeat_count"]
        elif kind == "ask":
            out.append(_line(voice, text, values["answer_pause"]))
        elif kind == "answer":
            out += [_line(voice, text, values["repeat_pause"])] * 2
        elif kind == "understand":
            out.append(f"{voice}: {text} [slow] [1 seconds]")
            out.append(_line(voice, text, 1))
        else:
            out.append(_line(voice, text, own_pause.group(1) if own_pause else 1))

    if problems:
        raise MarkupError("; ".join(problems))
    return "\n".join(out).strip() + "\n"


def top_up(marked, values, dialogue, heard, minutes):
    """
    The marked script with [respond] rounds of earlier dialogues added before
    the closing [dialogue], newest lesson first, skipping lessons it already
    rehearses, until the expanded lesson reaches `minutes` or there is nothing
    left to rehearse. Each round opens with the lesson's title, said by the
    Teacher: titles are written in the learner's own language.
    """
    lines = marked.rstrip("\n").split("\n")
    used = {int(m.group(1)) for m in (_RESPOND.match(l.strip()) for l in lines) if m}
    closing = max((i for i, l in enumerate(lines) if _DIALOGUE.match(l.strip())), default=len(lines))
    # Before the Teacher's line that introduces the closing dialogue ("Listen
    # again..."), not between it and the dialogue.
    before = closing - 1
    while before >= 0 and not lines[before].strip():
        before -= 1
    if before >= 0 and lines[before].strip().startswith("Teacher:"):
        closing = before
    target = minutes * 60 / SECONDS_PER_LINE

    added = []
    for n in range(len(heard), 0, -1):
        if expanded_line_count(lines + added, values, dialogue, heard) >= target:
            break
        if n in used or not heard[n - 1].dialogue or not heard[n - 1].learner:
            continue
        added += ["", f"Teacher: {heard[n - 1].title}.", f"[respond {n}]"]
    if not added:
        return marked
    return "\n".join(lines[:closing] + added + [""] + lines[closing:]) + "\n"


def expanded_line_count(lines, values, dialogue, heard):
    """Voice lines the marked script will have once expanded, without expanding it."""
    per_marker = {"drill": 1 + values["normal_speed_repeat_count"], "answer": 2, "understand": 2}
    count = 0
    for line in lines:
        line = line.strip()
        if _DIALOGUE.match(line):
            count += len(dialogue)
        elif respond := _RESPOND.match(line):
            n = int(respond.group(1))
            if 1 <= n <= len(heard) and heard[n - 1].dialogue:
                count += 2 * len(heard[n - 1].dialogue)
        elif voice_line := _VOICE_LINE.match(line):
            marker = _LINE_MARKER.search(voice_line.group(2))
            count += per_marker.get(marker.group(1).lower(), 1) if marker else 1
    return count

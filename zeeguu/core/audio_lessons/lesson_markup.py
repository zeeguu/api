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

A line with no marker is said once, followed by one second (or by the pause
it carries, when it has one). The expanded script is what is stored and
synthesized: nothing downstream knows about markers.

The review of earlier lessons is not the model's: code chooses it
(lesson_review.py) and places it before the closing dialogue (with_review).
Each reviewed dialogue is answered in the learner's role: the other person's
line, time to answer, the learner's line; then straight through.
"""

import re

from zeeguu.core.audio_lessons.lesson_tuning import SECONDS_PER_LINE

VOICES = ("Teacher", "TeacherL2", "Man", "Woman")
LINE_MARKERS = ("drill", "ask", "answer", "understand")

_VOICE_LINE = re.compile(r"^(Teacher|TeacherL2|Man|Woman):\s*(.*)$")
_LINE_MARKER = re.compile(r"\s*\[(drill|ask|answer|understand)\]\s*$", re.IGNORECASE)
_PAUSE = re.compile(r"\s*\[([0-9.]+)\s*seconds?\]\s*$", re.IGNORECASE)
_DIALOGUE = re.compile(r"^\[dialogue\]$", re.IGNORECASE)
_STANDALONE_ASK = re.compile(r"^\[ask\]$", re.IGNORECASE)
_ANY_MARKER = re.compile(r"\[([a-z][a-z ]*\d*)\]", re.IGNORECASE)
_KNOWN_INLINE = ("slow",)
# What the model writes when it means "no marker": twice in the eval it wrote
# one, echoing the prompt's wording ("[no marker]", "[plain]"). A plain line.
_PLAIN = re.compile(r"\s*\[(?:plain|no marker|none)\]\s*$", re.IGNORECASE)


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


def expand(script, values, dialogue):
    """
    The full script from a marked one.

    values: lesson_tuning.prompt_values; dialogue: this lesson's dialogue as
    [(voice, text)]. Raises MarkupError on a marker it cannot expand.
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

        if line.startswith("["):
            if _STANDALONE_ASK.match(line):
                # The model sometimes writes [ask] on a line of its own, after
                # the question, as it writes [dialogue] (4 of 17 eval lessons,
                # 20 Nov). It belongs to the Teacher line before it: without
                # it the learner gets one second to answer.
                previous = next((i for i in range(len(out) - 1, -1, -1) if out[i]), None)
                if previous is None or not out[previous].startswith("Teacher:"):
                    problems.append("[ask] on its own line, not after a Teacher line")
                else:
                    out[previous] = _PAUSE.sub("", out[previous]) + f" [{values['answer_pause']} seconds]"
            elif _PAUSE.fullmatch(line):
                out.append(line)
            else:
                problems.append(f"{line!r}: not a marker that stands on its own line")
            continue

        voice_line = _VOICE_LINE.match(line)
        if not voice_line:
            # The title: kept as it is.
            out.append(line)
            continue

        voice, text = voice_line.groups()
        text = _PLAIN.sub("", text)
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


def review_lines(reviews, values):
    """The review of earlier lessons (words_heard.HeardLesson), each opened by
    its title, said by the Teacher: titles are in the learner's own language."""
    out = []
    for lesson in reviews:
        out += ["", _line("Teacher", f"{lesson.title}.", 1)]
        out += respond_lines(lesson.dialogue, lesson.learner, values)
    return out


def with_review(expanded, review):
    """
    The expanded script with the review lines put before the closing dialogue:
    before the Teacher's line that introduces it ("Listen again..."), found
    as the last Teacher line. Nothing to put: the script as it was.
    """
    if not review:
        return expanded
    lines = expanded.rstrip("\n").split("\n")
    last_teacher = max((i for i, l in enumerate(lines) if l.startswith("Teacher:")), default=len(lines))
    return "\n".join(lines[:last_teacher] + review + [""] + lines[last_teacher:]) + "\n"


def voice_line_count(lines):
    return sum(1 for line in lines if _VOICE_LINE.match(line.strip()))

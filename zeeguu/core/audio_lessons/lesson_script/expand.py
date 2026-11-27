"""
The marked script, as the model wrote it (roles already relabeled as voices),
into the expanded script that is stored and synthesized: every repetition and
every pause added here, from the learner's tuning.
"""

import re
from dataclasses import replace

from zeeguu.core.audio_lessons.lesson_script.markers import (
    DIALOGUE_MARKER, LINE_MARKER, REVIEW_MARKER, REVIEW_SLOT, VOICE_LINE,
)
from zeeguu.core.audio_lessons.lesson_script.spoken_line import CHEVRON_SPAN, SpokenLine, spoken_lines, without_chevrons
from zeeguu.core.audio_lessons.lesson_script.time_to_answer import time_to_answer
from zeeguu.core.audio_lessons.lesson_script.voices import TEACHER, TEACHERS
from zeeguu.core.audio_lessons.words_heard import words_of

_PAUSE = re.compile(r"\s*\[([0-9.]+)\s*seconds?\]", re.IGNORECASE)
_ANY_MARKER = re.compile(r"\[([a-z][a-z ]*\d*)\]", re.IGNORECASE)
_KNOWN_INLINE = ("slow",)
# What the model writes when it means "no marker": twice in the eval it wrote
# one, echoing the prompt's wording ("[no marker]", "[plain]"). A plain line.
_PLAIN = re.compile(r"\s*\[(?:plain|no marker|none)\]\s*$", re.IGNORECASE)


class MarkupError(ValueError):
    """The script uses a marker wrongly; the message says how, for a rewrite."""


def expand(script, values, dialogue=None, learner=None, known_words=None, chevrons=True):
    """The expanded script as text (expand_lines, written out)."""
    lines = expand_lines(script, values, dialogue, learner, known_words, chevrons)
    return "\n".join(str(line) for line in lines).strip() + "\n"


def expand_lines(script, values, dialogue=None, learner=None, known_words=None, chevrons=True):
    """
    The full script from a marked one, its lines already labeled with voices,
    as SpokenLines (and blank lines as ""). [review] stays as REVIEW_SLOT,
    for with_review to fill.

    values: lesson_tuning.prompt_values; dialogue: this lesson's dialogue as
    [(voice, text)]; learner: the learner's voice, "man" or "woman";
    known_words: the learned-language words the learner heard before, which
    the Teacher may quote in «chevrons» (None: not checked).

    Lessons above A0 are shared between learners and written without a given
    dialogue or a learner's role: dialogue None (the script writes its
    dialogue out, and [dialogue] is refused), learner None (an answer's prompt
    is the line before it in another voice), chevrons False (« » are plain
    quotation marks, as French and Danish write them, and stay in the text).
    Raises MarkupError on a script it cannot expand.
    """
    out = []
    problems = []
    if known_words is not None:
        problems += foreign_chevron_spans(script, dialogue, known_words)
    for raw in script.split("\n"):
        line = raw.strip()
        if not line:
            out.append("")
            continue

        if REVIEW_MARKER.match(line):
            if REVIEW_SLOT in out:
                problems.append("[review] more than once: the review has one place")
            out.append(REVIEW_SLOT)
            continue

        if DIALOGUE_MARKER.match(line):
            if dialogue is None:
                problems.append("[dialogue]: write the dialogue out, line by line")
                continue
            if not any(isinstance(l, SpokenLine) and l.voice in TEACHERS for l in out):
                # The Teacher sets the scene first: heard cold, the dialogue
                # is noise to an absolute beginner.
                problems.append("[dialogue] before any Teacher line: set the scene first")
            out += [SpokenLine(voice, text, 1) for voice, text in dialogue]
            continue

        if line.startswith("["):
            # Only [dialogue] and [review] stand on a line of their own, and
            # the model writes no pauses. Anything else would be skipped
            # silently by the parser: a [drill] on its own line, say, would
            # leave its word undrilled.
            problems.append(f"{line!r}: not a marker that stands on its own line")
            continue

        voice_line = VOICE_LINE.match(line)
        if not voice_line:
            # Text under no label: a line the model wrapped, a bold label,
            # a preamble ("Here is your lesson:"). The prompt asks for none
            # (none in 45 eval lessons), and a guess at what it was could be
            # wrong, so the script is rewritten. The title is not here: it was
            # taken off before expanding (_write_dialogue_lesson).
            problems.append(f"{line!r}: a line without a voice label")
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
        if kind and voice == TEACHER:
            # [drill], [answer] and [understand] are what the learner says or
            # hears in the learned language; a Teacher line with one would be
            # said by the Teacher's voice, its «chevrons» unsplit.
            problems.append(f"{line!r}: [{kind}] on a Teacher line")
            continue
        text = re.sub(r"\s*\[slow\]", "", text, flags=re.IGNORECASE)
        if voice != TEACHER and chevrons:
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
            if prompt is not None and isinstance(out[prompt], SpokenLine) and out[prompt].voice != (learner or voice):
                out[prompt] = replace(out[prompt], pause=time_to_answer(text, values))
            out += [SpokenLine(voice, text, values["repeat_pause"])] * values["answer_repeats"]
        elif kind == "understand":
            out.append(SpokenLine(voice, text, 1, slow=True))
            out.append(SpokenLine(voice, text, 1))
        elif chevrons:
            out += spoken_lines(voice, text, 1)
        else:
            out.append(SpokenLine(voice, text, 1))

    if problems:
        raise MarkupError("; ".join(problems))
    return out



def foreign_chevron_spans(script, dialogue, known_words):
    """
    Problems with the «…» spans of the Teacher's lines: each word in one must
    be a learned-language word of this lesson (its learner's and other
    person's lines, its dialogue) or one the learner heard before. Catches a
    word of the Teacher's own language in chevrons ("the word for «very»")
    and a transliteration («blagodarya» for благодаря), which the
    learned-language voice would say wrongly; their language is not checked
    anywhere else, since the check leaves the spans out.
    """
    lesson_words = set()
    for raw in script.split("\n"):
        voice_line = VOICE_LINE.match(raw.strip())
        if voice_line and voice_line.group(1) not in ("Teacher", "TeacherL2"):
            lesson_words |= set(words_of(voice_line.group(2)))
    for _, text in dialogue:
        lesson_words |= set(words_of(text))
    allowed = lesson_words | {w.lower() for w in known_words}

    problems = []
    for raw in script.split("\n"):
        if not raw.strip().startswith("Teacher:"):
            continue
        for span in CHEVRON_SPAN.finditer(raw):
            unknown = [w for w in words_of(span.group(1)) if w not in allowed]
            if unknown:
                problems.append(
                    f"«{span.group(1)}»: chevrons hold only learned-language words of this lesson "
                    f"or earlier ones, as they are written ({', '.join(unknown)} is not one)"
                )
    return problems

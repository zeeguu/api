#!/usr/bin/env python
"""
Fill in learner_character and dialogue_script on A0 dialogues written before
they were stored (migration 26-11-20--add_learner_and_dialogue_to_audio_lesson_dialogue).

A one-off. New lessons store both when they are written; this infers them from
the script, once, for the ~60 older ones, and nothing else infers them:

- the dialogue is the last run of Man/Woman lines, since a lesson ends by
  playing its dialogue again; the opening run should be the same;
- the learner is the voice with the most lines, since their lines are drilled
  and recalled and the other person's only understood.

A row where either is doubtful is not written but listed for a person to look
at: the opening and closing dialogues differ (lesson 529 has a stray line), the
learner's voice has under 1.5x the other's lines (63 prod lessons: 1.6x-6.5x),
or the dialogue is shorter than 2 or longer than 10 lines. A row left NULL is
not rehearsed, which is safe.

Usage (dry run lists everything; --apply writes the rows that are not doubtful):
    python -m tools.backfill_a0_dialogue_learner [--apply]
"""

import argparse
from collections import Counter

from zeeguu.core.audio_lessons.script_parser import parse_script

MIN_RATIO = 1.5
MIN_LINES, MAX_LINES = 2, 10


def infer(script):
    """(dialogue as [(voice, text)], learner voice, list of doubts)."""
    runs, run = [], []
    lines = Counter()
    for voice, text, _ in parse_script(script or ""):
        if voice == "silence":
            continue
        if voice in ("man", "woman"):
            run.append((voice, text))
            lines[voice] += 1
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)
    if not runs:
        return (), None, ["no Man/Woman lines"]

    dialogue = tuple(runs[-1])
    (learner, most), *rest = lines.most_common()
    other = rest[0][1] if rest else 0

    doubts = []
    if tuple(runs[0]) != dialogue:
        doubts.append("opening and closing dialogues differ")
    if other and most / other < MIN_RATIO:
        doubts.append(f"learner has only {most / other:.1f}x the other's lines")
    if not MIN_LINES <= len(dialogue) <= MAX_LINES:
        doubts.append(f"dialogue has {len(dialogue)} lines")
    return dialogue, learner, doubts


def as_script(dialogue):
    return "\n".join(f"{voice.capitalize()}: {text}" for voice, text in dialogue)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write the rows that are not doubtful")
    args = parser.parse_args()

    from zeeguu.api.app import create_app_for_scripts

    app = create_app_for_scripts()
    app.app_context().push()
    from zeeguu.core.model import db
    from zeeguu.core.model.audio_lesson_dialogue import AudioLessonDialogue

    rows = (
        AudioLessonDialogue.query.filter(
            AudioLessonDialogue.builds_on_history.is_(True),
            AudioLessonDialogue.learner_character.is_(None),
        )
        .order_by(AudioLessonDialogue.id)
        .all()
    )
    written, doubtful = 0, []
    for row in rows:
        dialogue, learner, doubts = infer(row.script)
        if doubts:
            doubtful.append((row, doubts, dialogue, learner))
            continue
        print(f"{row.id}: {learner}, {len(dialogue)} lines")
        if args.apply:
            row.learner_character = learner
            row.dialogue_script = as_script(dialogue)
            written += 1

    for row, doubts, dialogue, learner in doubtful:
        print(f"\nDOUBTFUL {row.id} ({'; '.join(doubts)}), guess {learner}:")
        print(as_script(dialogue))

    if args.apply:
        db.session.commit()
    print(
        f"\n{len(rows)} rows: {len(rows) - len(doubtful)} clear, {len(doubtful)} doubtful (left NULL). "
        + (f"Wrote {written}." if args.apply else "Dry run: nothing written.")
    )


if __name__ == "__main__":
    main()

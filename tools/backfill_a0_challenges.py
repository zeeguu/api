#!/usr/bin/env python
"""
Give the A0 lessons written before challenges were kept their challenges,
so that later lessons can review them (audio_lessons/lesson_review.py).

A one-off, after migration 26-11-20-b and tools/backfill_a0_dialogue_learner
(which stores each old lesson's dialogue and the learner's role). From the
dialogue alone: each line of the learner after a line of the other person
is an exchange, without a setup (lesson_script.challenges.dialogue_challenges).
Lessons with no dialogue or no role stored (the doubtful ones of that
backfill) are skipped, and so are lessons that already have challenges.

Usage (dry run lists everything; --apply writes):
    python -m tools.backfill_a0_challenges [--apply]
"""

import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write the challenges")
    args = parser.parse_args()

    from zeeguu.api.app import create_app_for_scripts

    app = create_app_for_scripts()
    app.app_context().push()
    from zeeguu.core.audio_lessons.lesson_script.challenges import dialogue_challenges
    from zeeguu.core.audio_lessons.words_heard import stored_dialogue
    from zeeguu.core.model import db
    from zeeguu.core.model.audio_challenge import AudioChallenge
    from zeeguu.core.model.audio_lesson_dialogue import AudioLessonDialogue

    have_challenges = {row.dialogue_id for row in AudioChallenge.query.with_entities(AudioChallenge.dialogue_id)}
    rows = (
        AudioLessonDialogue.query.filter(AudioLessonDialogue.builds_on_history.is_(True))
        .order_by(AudioLessonDialogue.id)
        .all()
    )
    lessons = written = skipped = 0
    for row in rows:
        if row.id in have_challenges:
            continue
        if not row.dialogue_script or not row.learner_character:
            skipped += 1
            continue
        found = dialogue_challenges(stored_dialogue(row), row.learner_character)
        lessons += 1
        print(f"{row.id}: {len(found)} challenges")
        for challenge in found:
            print(f"    {challenge.prompt.voice}: {challenge.prompt.text}  ->  {challenge.answer.text}")
        if args.apply:
            for position, challenge in enumerate(found):
                db.session.add(AudioChallenge(row.id, position, challenge))
                written += 1

    if args.apply:
        db.session.commit()
    print(
        f"\n{lessons} lessons, {skipped} skipped (no dialogue or role stored). "
        + (f"Wrote {written} challenges." if args.apply else "Dry run: nothing written.")
    )


if __name__ == "__main__":
    main()

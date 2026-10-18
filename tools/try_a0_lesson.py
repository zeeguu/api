#!/usr/bin/env python
"""
Write an A0 audio lesson script without touching the database, to read (or
listen to) while the A0 prompt is being tuned.

A sequence is simulated by passing the scripts of the earlier lessons: their
words become the learner's history, exactly as words_heard builds it in
production from the lessons a user engaged with.

Usage:
    python -m tools.try_a0_lesson --situation "at the café" --out /tmp/a0-1.txt
    python -m tools.try_a0_lesson --situation "in a clothes shop" \\
        --after /tmp/a0-1.txt --out /tmp/a0-2.txt
    python -m tools.try_a0_lesson --language da --teacher de --situation "..."

Prints the history table it used, the title, and statistics on the script:
new words, and how often each word of this lesson is said.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.audio_lessons.script_generator import generate_dialogue_script
from zeeguu.core.audio_lessons.words_heard import (
    HeardLesson,
    history_table,
    target_language_words,
)


def _earlier(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    title, _, script = text.partition("\n\n")
    return HeardLesson(title.strip() or os.path.basename(path), target_language_words(script))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--situation")
    parser.add_argument("--language", default="da", help="language learned (default da)")
    parser.add_argument("--teacher", default="en", help="language the teacher speaks (default en)")
    parser.add_argument("--after", nargs="*", default=[], help="scripts of the earlier lessons, in order")
    parser.add_argument("--character", choices=["man", "woman"], help="the character the learner plays (default: alternate)")
    parser.add_argument("--out", help="where to write the title and script")
    parser.add_argument(
        "--audio",
        action="store_true",
        help="also voice it, with the app's voices, next to --out as .mp3 (Google TTS)",
    )
    parser.add_argument(
        "--voice-only",
        metavar="SCRIPT",
        help="only voice an existing script written by this tool, no new lesson",
    )
    args = parser.parse_args()

    if args.voice_only:
        _, _, script = open(args.voice_only, encoding="utf-8").read().partition("\n\n")
        _voice(script, args.voice_only, args.language, args.teacher)
        return
    if not (args.situation and args.out):
        parser.error("--situation and --out are required unless --voice-only")

    heard = [_earlier(p) for p in args.after]
    history = history_table(heard)
    print("History given to the model:")
    print(history or "(none: first lesson)")
    print()

    title, generated = generate_dialogue_script(
        origin_language=args.language,
        translation_language=args.teacher,
        suggestion=args.situation,
        lesson_type="situation",
        cefr_level="A0",
        heard=heard,
        # The chosen character, else the two take turns over the earlier lessons
        # given, as the app does over all of a user's lessons of this kind.
        learner_character=args.character or ("man" if len(heard) % 2 == 0 else "woman"),
    )

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(f"{title}\n\n{generated.script}\n")

    words = target_language_words(generated.script)
    known = set().union(*(h.words for h in heard)) if heard else set()
    new = {w: c for w, c in words.items() if w not in known}
    lines = generated.script.count("\n") + 1

    print(f"Title:  {title}")
    print(f"Model:  {generated.model_name}, prompt {generated.prompt_version}")
    print(f"Lines:  {lines}")
    print(f"Words:  {sum(words.values())} said, {len(words)} distinct, {len(new)} new")
    print("New:    " + ", ".join(f"{w} {c}" for w, c in sorted(new.items(), key=lambda x: -x[1])))
    reused = {w: c for w, c in words.items() if w in known}
    if reused:
        print("Reused: " + ", ".join(f"{w} {c}" for w, c in sorted(reused.items(), key=lambda x: -x[1])))
    print(f"\nWritten to {args.out}")

    if args.audio:
        _voice(generated.script, args.out, args.language, args.teacher)


def _voice(script, script_path, language, teacher):
    from zeeguu.core.audio_lessons.voice_synthesizer import VoiceSynthesizer

    mp3 = os.path.splitext(script_path)[0] + ".mp3"
    # The same path the app takes for a lesson, minus the row id in the filename.
    VoiceSynthesizer()._synthesize_script_to_file(
        script, mp3, language, teacher, cefr_level="A0", variety=None
    )
    print(f"Voiced to {mp3}")


if __name__ == "__main__":
    main()

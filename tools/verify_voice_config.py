#!/usr/bin/env python
"""
Check every voice name in VOICE_CONFIG against what Google actually offers.

The one thing the test suite cannot do. A voice id is a string we wrote down
from a catalogue, and a wrong one does not fail at import or in CI -- it fails
at synthesis time, for every learner of that language, once the code is live.
Adding a locale to VOICE_CONFIG (a variety, a new language) is exactly when that
string is most likely to be a guess, so run this then.

    GOOGLE_APPLICATION_CREDENTIALS=<creds.json> python tools/verify_voice_config.py

Needs no database and no app context; it only talks to Google.
"""

import sys

from google.cloud import texttospeech

from zeeguu.core.audio_lessons.voice_config import DEFAULT_LOCALE, VOICE_CONFIG


def main():
    available = {voice.name for voice in texttospeech.TextToSpeechClient().list_voices().voices}

    missing = [
        (locale, role, name)
        for locale, voices in VOICE_CONFIG.items()
        for role, name in voices.items()
        if role != "provider" and name not in available
    ]

    for locale in sorted(VOICE_CONFIG):
        default = " (default)" if DEFAULT_LOCALE.get(locale.split("-")[0]) == locale else ""
        broken = [role for loc, role, _ in missing if loc == locale]
        status = f"MISSING: {', '.join(broken)}" if broken else "ok"
        print(f"  {locale:6} {status}{default}")

    if missing:
        print(f"\n{len(missing)} voice(s) Google does not offer:")
        for locale, role, name in missing:
            print(f"  {locale} {role}: {name}")
        print("\nEvery lesson in those locales would fail at synthesis.")
        return 1

    print(f"\nAll {sum(len(v) for v in VOICE_CONFIG.values())} configured voices exist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

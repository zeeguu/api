#!/usr/bin/env python
"""
Generate audio for Danish text using Google Cloud TTS.

Usage:
    source ~/.venvs/z_env/bin/activate && python -m tools.generate_danish_audio
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app
from zeeguu.core.audio_lessons.voice_synthesizer import VoiceSynthesizer

app = create_app()
app.app_context().push()

TITLE = "Alkoholkultur"

PARAGRAPHS = [
    "Mange voksne og unge mennesker i Danmark drikker meget alkohol. Mange unge drikker meget alkohol på en gang, når de er sammen med andre unge (fx til en fest, når de går i byen). De gør det, fordi de føler noget godt, når de drikker alkohol sammen med andre (se hygge).",
    "Nogle mennesker i Danmark kan tænke, at det er lidt dårligt, hvis en person ikke drikker alkohol (fx når de spiser sammen, når de er til fest sammen). Måske tænker de, at personen ikke vil føle noget godt sammen med de andre (se fællesskab). Nogle mennesker i Danmark tænker, at det er svært at sige nej til alkohol på grund af det. Ofte vil folk spørge en person, som ikke drikker alkohol, hvorfor personen ikke gør det.",
    "Staten i Danmark siger, at det ikke er godt at drikke alkohol. Det er ikke godt for kroppen.",
]


def main():
    from pydub import AudioSegment
    import io

    print("Initializing VoiceSynthesizer...")
    synthesizer = VoiceSynthesizer()

    # Danish female voice (Wavenet-A) or male voice (Wavenet-G)
    voice_config = {
        "language_code": "da-DK",
        "name": "da-DK-Wavenet-A",  # Female voice. Use "da-DK-Wavenet-G" for male
    }

    speaking_rate = 0.8
    title_pause_ms = 1500  # 1.5 seconds after title
    paragraph_pause_ms = 1000  # 1 second between paragraphs

    print(f"Generating audio with voice: {voice_config['name']}")

    audio_segments = []

    # Generate title audio
    print(f"Generating title: {TITLE}")
    title_bytes = synthesizer.text_to_speech(TITLE, voice_config, speaking_rate)
    audio_segments.append(AudioSegment.from_mp3(io.BytesIO(title_bytes)))
    audio_segments.append(AudioSegment.silent(duration=title_pause_ms))

    # Generate paragraph audio with pauses between them
    for i, paragraph in enumerate(PARAGRAPHS):
        print(f"Generating paragraph {i + 1}/{len(PARAGRAPHS)}...")
        para_bytes = synthesizer.text_to_speech(paragraph, voice_config, speaking_rate)
        audio_segments.append(AudioSegment.from_mp3(io.BytesIO(para_bytes)))

        # Add pause after each paragraph except the last
        if i < len(PARAGRAPHS) - 1:
            audio_segments.append(AudioSegment.silent(duration=paragraph_pause_ms))

    # Combine all segments
    combined = audio_segments[0]
    for segment in audio_segments[1:]:
        combined += segment

    output_file = "alkoholkultur.mp3"
    combined.export(output_file, format="mp3")

    print(f"Audio saved to: {os.path.abspath(output_file)}")
    print(f"Duration: {combined.duration_seconds:.1f} seconds")


if __name__ == "__main__":
    main()

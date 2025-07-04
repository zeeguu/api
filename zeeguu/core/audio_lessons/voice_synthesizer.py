"""
Voice synthesizer for audio lessons using Google Cloud Text-to-Speech.
"""

import os
import re
import hashlib
from typing import List, Tuple
from google.cloud import texttospeech
from pydub import AudioSegment

from zeeguu.config import ZEEGUU_DATA_FOLDER
from zeeguu.core.audio_lessons.voice_config import (
    get_voice_id,
    get_teacher_voice,
    normalize_language_code,
    DEFAULT_SILENCE_SECONDS,
)
from zeeguu.logging import log


class VoiceSynthesizer:
    """Handles text-to-speech synthesis and audio file management."""

    def __init__(self):
        """Initialize the Google Cloud TTS client."""
        self.client = texttospeech.TextToSpeechClient()
        self.audio_dir = ZEEGUU_DATA_FOLDER + "/audio"
        self.lessons_dir = os.path.join(self.audio_dir, "lessons")
        self.segments_dir = os.path.join(self.audio_dir, "segments")

        # Create directories if they don't exist
        os.makedirs(self.lessons_dir, exist_ok=True)
        os.makedirs(self.segments_dir, exist_ok=True)

    def parse_script(self, script: str) -> List[Tuple[str, str, float]]:
        """
        Parse the script into individual voice segments.

        Returns:
            List of tuples: (voice_type, text, silence_after)
        """
        segments = []
        lines = script.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Handle silence markers like [1 second silence]
            if line.startswith("[") and "silence" in line.lower():
                # Extract duration from patterns like "[1 second silence]"
                duration_match = re.search(
                    r"\[([0-9.]+)\s*second[s]?\s*silence\]", line, re.IGNORECASE
                )
                if duration_match:
                    duration = float(duration_match.group(1))
                    segments.append(("silence", "", duration))
                continue

            # Parse voice lines like "Teacher: Some text [2 seconds]"
            voice_match = re.match(r"^(Teacher|Man|Woman):\s*(.+)$", line)
            if not voice_match:
                continue

            voice_type = voice_match.group(1).lower()
            text = voice_match.group(2)

            # Check for silence duration at end of line
            silence_duration = DEFAULT_SILENCE_SECONDS
            silence_match = re.search(r"\[([0-9.]+)\s*seconds?\]$", text)
            if silence_match:
                silence_duration = float(silence_match.group(1))
                text = re.sub(r"\s*\[[0-9.]+\s*seconds?\]$", "", text)

            segments.append((voice_type, text.strip(), silence_duration))

        return segments

    def get_voice_config(self, voice_type: str, language_code: str) -> dict:
        """Get the voice configuration for TTS."""
        if voice_type == "teacher":
            voice_id = get_teacher_voice()
            language = "en-US"
        else:
            # Normalize the language code and get the voice
            normalized_language = normalize_language_code(language_code)
            voice_id = get_voice_id(language_code, voice_type)
            language = normalized_language

        return {"language_code": language, "name": voice_id}

    def text_to_speech(
        self, text: str, voice_config: dict, speaking_rate: float = 1.0
    ) -> bytes:
        """Convert text to speech using Google Cloud TTS."""
        synthesis_input = texttospeech.SynthesisInput(text=text)

        voice = texttospeech.VoiceSelectionParams(
            language_code=voice_config["language_code"], name=voice_config["name"]
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=speaking_rate
        )

        response = self.client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        return response.audio_content

    def get_cached_audio_path(
        self, text: str, voice_id: str, speaking_rate: float = 1.0
    ) -> str:
        """Get the cached audio file path for given text and voice."""
        # Create a hash of the text, voice, and speaking rate for filename
        content_hash = hashlib.md5(
            f"{voice_id}:{text}:{speaking_rate}".encode("utf-8")
        ).hexdigest()
        return os.path.join(self.segments_dir, f"{voice_id}_{content_hash}.mp3")

    def synthesize_segment(
        self, text: str, voice_type: str, language_code: str, speaking_rate: float = 1.0
    ) -> str:
        """
        Synthesize a single text segment and cache it.

        Returns:
            Path to the generated MP3 file
        """
        voice_config = self.get_voice_config(voice_type, language_code)
        voice_id = voice_config["name"]

        # Check if we already have this audio cached
        cached_path = self.get_cached_audio_path(text, voice_id, speaking_rate)
        if os.path.exists(cached_path):
            log(f"Using cached audio for: {text[:50]}...")
            return cached_path

        # Generate new audio
        log(
            f"Generating TTS for ({voice_type}) at {speaking_rate}x speed: {text[:50]}..."
        )
        audio_content = self.text_to_speech(text, voice_config, speaking_rate)

        # Save to cache
        with open(cached_path, "wb") as f:
            f.write(audio_content)

        return cached_path

    def generate_lesson_audio(
        self,
        audio_lesson_meaning_id: int,
        script: str,
        language_code: str,
        cefr_level: str = None,
    ) -> str:
        """
        Generate the complete audio lesson from script.

        Returns:
            Path to the generated MP3 file
        """
        segments = self.parse_script(script)
        audio_segments = []

        # Determine speaking rate based on CEFR level
        speaking_rate = 1.0
        if cefr_level:
            if cefr_level == "A2":
                speaking_rate = 0.9
            elif cefr_level == "A1":
                speaking_rate = 0.8

        for voice_type, text, silence_duration in segments:
            if voice_type == "silence":
                # Add silence - silence_duration contains the duration in seconds
                silence = AudioSegment.silent(
                    duration=silence_duration * 1000
                )  # Convert to milliseconds
                audio_segments.append(silence)
            else:
                # Generate speech
                audio_path = self.synthesize_segment(
                    text, voice_type, language_code, speaking_rate
                )
                audio_segment = AudioSegment.from_mp3(audio_path)
                audio_segments.append(audio_segment)

                # Add silence after speech (if specified)
                if silence_duration > 0:
                    silence = AudioSegment.silent(duration=silence_duration * 1000)
                    audio_segments.append(silence)

        # Combine all audio segments
        if audio_segments:
            combined_audio = audio_segments[0]
            for segment in audio_segments[1:]:
                combined_audio += segment
        else:
            # Empty audio if no segments
            combined_audio = AudioSegment.silent(duration=1000)  # 1 second silence

        # Save the final lesson audio
        output_path = os.path.join(self.lessons_dir, f"{audio_lesson_meaning_id}.mp3")
        combined_audio.export(output_path, format="mp3")

        log(f"Generated lesson audio: {output_path}")
        return output_path

    def get_audio_duration(self, audio_path: str) -> int:
        """Get the duration of an audio file in seconds."""
        audio = AudioSegment.from_mp3(audio_path)
        return int(audio.duration_seconds)

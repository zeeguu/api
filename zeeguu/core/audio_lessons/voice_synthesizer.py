"""
Voice synthesizer for audio lessons using Google Cloud Text-to-Speech and Azure TTS.
Uses Azure for languages not well-supported by Google (e.g., Greek with male voices).
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
    VOICE_CONFIG,
)
from zeeguu.core.audio_lessons.azure_voice_synthesizer import AzureVoiceSynthesizer
from zeeguu.logging import log


class VoiceSynthesizer:
    """Handles text-to-speech synthesis and audio file management."""

    def __init__(self):
        """Initialize the Google Cloud TTS client and Azure TTS client if needed."""
        self.google_client = texttospeech.TextToSpeechClient()

        # Initialize Azure client (lazy initialization on first use)
        self.azure_client = None

        self.audio_dir = ZEEGUU_DATA_FOLDER + "/audio"
        self.lessons_dir = os.path.join(self.audio_dir, "lessons")
        self.segments_dir = os.path.join(self.audio_dir, "segments")

        # Create directories if they don't exist
        os.makedirs(self.lessons_dir, exist_ok=True)
        os.makedirs(self.segments_dir, exist_ok=True)

    def _uses_azure(self, language_code: str) -> bool:
        """Check if this language uses Azure instead of Google."""
        try:
            full_code = normalize_language_code(language_code)
            config = VOICE_CONFIG.get(full_code, {})
            return config.get("provider") == "azure"
        except ValueError:
            return False

    def _get_azure_client(self) -> AzureVoiceSynthesizer:
        """Get or create the Azure TTS client (lazy initialization)."""
        if self.azure_client is None:
            self.azure_client = AzureVoiceSynthesizer()
        return self.azure_client

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
            voice_match = re.match(r"^(Teacher|Man|Woman|Armin|Aldo):\s*(.+)$", line, re.IGNORECASE)
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

    def get_voice_config(self, voice_type: str, language_code: str, teacher_language: str = None) -> dict:
        """Get the voice configuration for TTS.
        
        Args:
            voice_type: Type of voice (teacher, man, woman)
            language_code: Language code for the target language
            teacher_language: Optional language code for teacher voice (defaults to English)
        """
        if voice_type == "teacher":
            # If teacher_language is specified, use that language's teacher voice
            if teacher_language:
                normalized_language = normalize_language_code(teacher_language)
                voice_id = get_voice_id(teacher_language, "teacher")
                language = normalized_language
            else:
                # Default to English teacher voice
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
        """
        Convert text to speech using Google Cloud TTS or Azure TTS.
        Routes to appropriate provider based on language configuration.
        """
        language_code = voice_config["language_code"]
        voice_name = voice_config["name"]

        # Check if we should use Azure for this language
        if self._uses_azure(language_code):
            log(f"Using Azure TTS for {language_code}")
            azure_client = self._get_azure_client()
            return azure_client.text_to_speech(
                text=text,
                voice_id=voice_name,
                speaking_rate=speaking_rate,
                language_code=language_code,
            )
        else:
            # Use Google TTS (default)
            synthesis_input = texttospeech.SynthesisInput(text=text)

            voice = texttospeech.VoiceSelectionParams(
                language_code=language_code, name=voice_name
            )

            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=speaking_rate,
            )

            response = self.google_client.synthesize_speech(
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
        self, text: str, voice_type: str, language_code: str, speaking_rate: float = 1.0, teacher_language: str = None
    ) -> str:
        """
        Synthesize a single text segment and cache it.

        Returns:
            Path to the generated MP3 file
        """
        voice_config = self.get_voice_config(voice_type, language_code, teacher_language)
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
        teacher_language: str = None,
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
                speaking_rate = 0.9  # 0.8 was painfully slow for Portuguese; this might end up being language specific? or maybe a setting for the frontend

        for voice_type, text, silence_duration in segments:
            if voice_type == "silence":
                # Add silence - silence_duration contains the duration in seconds
                silence = AudioSegment.silent(
                    duration=silence_duration * 1000
                )  # Convert to milliseconds
                audio_segments.append(silence)
            else:
                # Generate speech
                # Apply speaking rate slowdown only to man and woman voices, not teacher
                rate = speaking_rate if voice_type in ["man", "woman"] else 1.0
                audio_path = self.synthesize_segment(
                    text, voice_type, language_code, rate, teacher_language
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
        try:
            audio = AudioSegment.from_mp3(audio_path)
            return int(audio.duration_seconds)
        except Exception as e:
            log(f"Warning: Could not get audio duration from {audio_path}: {str(e)}")
            log("Falling back to estimated duration based on file size")

            # Fallback: estimate duration based on file size
            # Typical MP3 bitrate is around 128 kbps for speech
            # File size in bytes / (bitrate in bits per second / 8) = duration in seconds
            try:
                file_size_bytes = os.path.getsize(audio_path)
                # Estimate: 128 kbps = 16 KB/s, but Google TTS usually uses lower bitrates
                # Use conservative estimate of 12 KB/s for speech
                estimated_duration = file_size_bytes / (12 * 1024)  # 12 KB/s
                return max(1, int(estimated_duration))  # At least 1 second
            except Exception as fallback_error:
                log(f"Error in fallback duration calculation: {str(fallback_error)}")
                # Return a reasonable default for a single word lesson segment
                return 3

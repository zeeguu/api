"""
Lesson builder for combining individual audio lessons into daily lessons.
"""

import os
from pydub import AudioSegment

from zeeguu.config import ZEEGUU_DATA_FOLDER
from zeeguu.core.model import DailyAudioLesson
from zeeguu.logging import log


class LessonBuilder:
    """Handles building complete daily lessons from individual segments."""

    def __init__(self):
        self.audio_dir = ZEEGUU_DATA_FOLDER + "/audio"
        self.daily_lessons_dir = os.path.join(self.audio_dir, "daily_lessons")

        # Create directory if it doesn't exist
        os.makedirs(self.daily_lessons_dir, exist_ok=True)

    def build_daily_lesson(self, daily_lesson: DailyAudioLesson) -> str:
        """
        Build a complete daily lesson by concatenating all segment audio files.

        Args:
            daily_lesson: The DailyAudioLesson instance with segments

        Returns:
            Path to the generated daily lesson MP3 file
        """
        audio_segments = []

        # Process segments in order
        for segment in daily_lesson.segments:
            audio_path = None

            if (
                segment.segment_type == "meaning_lesson"
                and segment.audio_lesson_meaning
            ):
                # Use the individual meaning lesson audio
                relative_path = segment.audio_lesson_meaning.audio_file_path
                # Remove leading /audio/ since we're already in /$ZEEGUU_DATA_FOLDER/audio
                if relative_path.startswith("/audio/"):
                    relative_path = relative_path[7:]  # Remove '/audio/'
                audio_path = os.path.join(self.audio_dir, relative_path)
            elif (
                segment.segment_type in ["intro", "outro"]
                and segment.daily_audio_lesson_wrapper
            ):
                # Use the wrapper audio
                relative_path = segment.daily_audio_lesson_wrapper.audio_file_path
                audio_path = os.path.join(self.audio_dir, relative_path.lstrip("/"))
            else:
                audio_path = None

            if audio_path and os.path.exists(audio_path):
                log(f"Adding segment audio: {audio_path}")
                audio_segment = AudioSegment.from_mp3(audio_path)
                audio_segments.append(audio_segment)
            else:
                log(
                    f"Warning: Audio file not found for segment {segment.id}: {audio_path}"
                )

        # Combine all audio segments
        if audio_segments:
            combined_audio = audio_segments[0]
            for segment in audio_segments[1:]:
                combined_audio += segment
        else:
            # Create a short silence if no audio segments
            log("Warning: No audio segments found, creating empty lesson")
            combined_audio = AudioSegment.silent(duration=1000)  # 1 second silence

        # Save the final daily lesson audio
        output_path = os.path.join(self.daily_lessons_dir, f"{daily_lesson.id}.mp3")
        combined_audio.export(output_path, format="mp3")

        log(f"Generated daily lesson audio: {output_path}")
        return output_path

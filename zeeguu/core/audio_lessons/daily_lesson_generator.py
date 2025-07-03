"""
Daily lesson generator for creating audio lessons from user words.
"""

import time

from zeeguu.core.audio_lessons.lesson_builder import LessonBuilder
from zeeguu.core.audio_lessons.script_generator import generate_lesson_script
from zeeguu.core.audio_lessons.voice_synthesizer import VoiceSynthesizer
from zeeguu.core.model import (
    db,
    User,
    Meaning,
    AudioLessonMeaning,
    DailyAudioLesson,
    DailyAudioLessonSegment,
)
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
from zeeguu.logging import log


class DailyLessonGenerator:
    """Generates daily audio lessons for users."""

    def __init__(self):
        self.voice_synthesizer = VoiceSynthesizer()
        self.lesson_builder = LessonBuilder()

    def generate_daily_lesson(self, user: User, num_words: int = 3) -> dict:
        """
        Generate a daily audio lesson for the given user.

        Args:
            user: The user to generate lesson for
            num_words: Number of words to include in the lesson (default 3)

        Returns:
            Dictionary with lesson details or error information
        """
        start_time = time.time()

        try:
            # Get user's words that are currently being learned
            learning_words = BasicSRSchedule.user_words_to_study(user)

            # Filter out words that have already been in audio lessons for this user
            meanings_already_in_lessons = (
                db.session.query(Meaning.id)
                .join(AudioLessonMeaning, AudioLessonMeaning.meaning_id == Meaning.id)
                .join(
                    DailyAudioLessonSegment,
                    DailyAudioLessonSegment.audio_lesson_meaning_id
                    == AudioLessonMeaning.id,
                )
                .join(
                    DailyAudioLesson,
                    DailyAudioLesson.id
                    == DailyAudioLessonSegment.daily_audio_lesson_id,
                )
                .filter(DailyAudioLesson.user_id == user.id)
                .distinct()
                .all()
            )

            existing_meaning_ids = {m[0] for m in meanings_already_in_lessons}

            # Filter and rank words by importance
            available_words = []
            for user_word in learning_words:
                if user_word.meaning_id not in existing_meaning_ids:
                    # Get word rank for importance ranking
                    origin_word = user_word.meaning.origin.content
                    try:
                        from wordstats import Word

                        word_stats = Word.stats(
                            origin_word, user_word.meaning.origin.language.code
                        )
                        rank = word_stats.rank if word_stats else 999999
                    except:
                        rank = 999999

                    available_words.append((user_word, rank))

            # Sort by rank (lower is more important) and take top N
            available_words.sort(key=lambda x: x[1])
            selected_words = [w[0] for w in available_words[:num_words]]

            if len(selected_words) < num_words:
                return {
                    "error": f"Not enough new words to generate a lesson. Need at least {num_words} words.",
                    "available_words": len(selected_words),
                }

            # Create daily lesson
            daily_lesson = DailyAudioLesson(
                user=user, created_by="generate_daily_lesson_v1"
            )
            db.session.add(daily_lesson)

            # Generate audio lesson for each selected word
            for idx, user_word in enumerate(selected_words):
                meaning = user_word.meaning

                # Generate script using Claude
                try:
                    script = generate_lesson_script(
                        origin_word=meaning.origin.content,
                        translation_word=meaning.translation.content,
                        origin_language=meaning.origin.language.code,
                        translation_language=meaning.translation.language.code,
                        cefr_level=user.cefr_level_for_learned_language(),
                    )
                except Exception as e:
                    log(
                        f"Failed to generate script for {meaning.origin.content}: {str(e)}"
                    )
                    db.session.rollback()
                    return {
                        "error": f"Failed to generate script: {str(e)}",
                        "word": meaning.origin.content,
                    }

                # Create audio lesson meaning
                audio_lesson_meaning = AudioLessonMeaning(
                    meaning=meaning,
                    script=script,
                    created_by="claude-v1",
                    difficulty_level=user.cefr_level_for_learned_language(),  # Default to B1 for now
                )
                db.session.add(audio_lesson_meaning)
                db.session.flush()  # Get the ID

                # Generate MP3 from script
                try:
                    mp3_path = self.voice_synthesizer.generate_lesson_audio(
                        audio_lesson_meaning_id=audio_lesson_meaning.id,
                        script=script,
                        language_code=meaning.origin.language.code,
                        cefr_level=user.cefr_level_for_learned_language(),
                    )

                    # Calculate duration
                    duration_seconds = self.voice_synthesizer.get_audio_duration(
                        mp3_path
                    )
                    audio_lesson_meaning.duration_seconds = duration_seconds

                except Exception as e:
                    log(
                        f"Failed to generate audio for {meaning.origin.content}: {str(e)}"
                    )
                    db.session.rollback()
                    return {
                        "error": f"Failed to generate audio: {str(e)}",
                        "word": meaning.origin.content,
                    }

                # Add segment to daily lesson
                daily_lesson.add_meaning_segment(
                    audio_lesson_meaning=audio_lesson_meaning, sequence_order=idx + 1
                )

            # Build the final concatenated MP3 for the daily lesson
            try:
                daily_mp3_path = self.lesson_builder.build_daily_lesson(daily_lesson)

                # Calculate total duration
                total_duration = self.voice_synthesizer.get_audio_duration(
                    daily_mp3_path
                )
                daily_lesson.duration_seconds = total_duration

            except Exception as e:
                log(f"Failed to build daily lesson: {str(e)}")
                db.session.rollback()
                return {"error": f"Failed to build daily lesson: {str(e)}"}

            db.session.commit()

            end_time = time.time()
            generation_time = end_time - start_time
            log(f"Daily lesson generation completed in {generation_time:.2f} seconds")

            return {
                "lesson_id": daily_lesson.id,
                "audio_url": f"/audio/daily_lessons/{daily_lesson.id}.mp3",
                "duration_seconds": daily_lesson.duration_seconds,
                "generation_time_seconds": round(generation_time, 2),
                "words": [
                    {
                        "origin": w.meaning.origin.content,
                        "translation": w.meaning.translation.content,
                    }
                    for w in selected_words
                ],
            }

        except Exception as e:
            db.session.rollback()
            log(f"Unexpected error in daily lesson generation: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}"}

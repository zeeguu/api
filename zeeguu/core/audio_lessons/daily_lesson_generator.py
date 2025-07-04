"""
Daily lesson generator for creating audio lessons from user words.
"""

import os
import time
from datetime import datetime, date

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
from zeeguu.config import ZEEGUU_DATA_FOLDER
from zeeguu.logging import log


class DailyLessonGenerator:
    """Generates daily audio lessons for users."""

    def __init__(self):
        self.voice_synthesizer = VoiceSynthesizer()
        self.lesson_builder = LessonBuilder()

    def generate_daily_lesson_for_user(self, user):
        """
        Generate a daily audio lesson for a user with automatic word selection.
        This is the main entry point for generating lessons from the API.
        
        Args:
            user: The User object to generate a lesson for
            
        Returns:
            Dictionary with lesson details or error information
        """
        # Check if user has access to daily audio lessons
        if not user.has_feature("daily_audio"):
            return {
                "error": "Daily audio lessons are not available for your account",
                "status_code": 403
            }

        # Select words for the lesson
        selected_words = self.select_words_for_lesson(user, 3)
        if len(selected_words) < 3:
            return {
                "error": f"Not enough new words to generate a lesson. Need at least 3 words.",
                "available_words": len(selected_words),
                "status_code": 400
            }

        # Get user's languages and CEFR level
        origin_language = user.learned_language.code
        translation_language = user.native_language.code
        cefr_level = user.cefr_level_for_learned_language()

        # Generate the lesson
        return self.generate_daily_lesson(
            user=user,
            selected_words=selected_words,
            origin_language=origin_language,
            translation_language=translation_language,
            cefr_level=cefr_level,
        )

    def select_words_for_lesson(self, user: User, num_words: int = 3) -> list:
        """
        Select words for a daily audio lesson.

        Args:
            user: The user to select words for
            num_words: Number of words to select (default 3)

        Returns:
            List of UserWord objects, or empty list if not enough words available
        """
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

        return selected_words

    def generate_daily_lesson(self, user: User, selected_words: list, origin_language: str, 
                            translation_language: str, cefr_level: str) -> dict:
        """
        Generate a daily audio lesson for the given user with specific words.

        Args:
            user: The user to generate lesson for (for lesson ownership)
            selected_words: List of UserWord objects to include in the lesson
            origin_language: Language code for the words being learned (e.g. 'es', 'da')
            translation_language: Language code for translations (e.g. 'en')
            cefr_level: CEFR level for the lesson (e.g. 'A1', 'B2')

        Returns:
            Dictionary with lesson details or error information
        """
        start_time = time.time()

        try:

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
                        origin_language=origin_language,
                        translation_language=translation_language,
                        cefr_level=cefr_level,
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
                    difficulty_level=cefr_level,
                )
                db.session.add(audio_lesson_meaning)
                db.session.flush()  # Get the ID

                # Generate MP3 from script
                try:
                    mp3_path = self.voice_synthesizer.generate_lesson_audio(
                        audio_lesson_meaning_id=audio_lesson_meaning.id,
                        script=script,
                        language_code=origin_language,
                        cefr_level=cefr_level,
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

    def _check_user_access(self, user):
        """Check if user has access to daily audio lessons."""
        if not user.has_feature("daily_audio"):
            return {
                "error": "Daily audio lessons are not available for your account",
                "status_code": 403
            }
        return None

    def _format_lesson_response(self, lesson):
        """Format a lesson into the standard response format."""
        # Check if audio file exists
        audio_path = os.path.join(
            ZEEGUU_DATA_FOLDER, "audio", "daily_lessons", f"{lesson.id}.mp3"
        )

        if not os.path.exists(audio_path):
            return {
                "error": "Audio file not found for this lesson",
                "status_code": 404
            }

        # Get lesson details including words
        words = []
        for segment in lesson.segments:
            if segment.segment_type == "meaning_lesson" and segment.audio_lesson_meaning:
                meaning = segment.audio_lesson_meaning.meaning
                words.append(
                    {
                        "origin": meaning.origin.content,
                        "translation": meaning.translation.content,
                    }
                )

        return {
            "lesson_id": lesson.id,
            "audio_url": f"/audio/daily_lessons/{lesson.id}.mp3",
            "duration_seconds": lesson.duration_seconds,
            "created_at": lesson.created_at.isoformat() if lesson.created_at else None,
            "words": words,
        }

    def get_daily_lesson_for_user(self, user, lesson_id=None):
        """
        Get a daily audio lesson for a user.
        
        Args:
            user: The User object
            lesson_id: Optional specific lesson ID to retrieve
            
        Returns:
            Dictionary with lesson details or error information
        """
        # Check user access
        access_error = self._check_user_access(user)
        if access_error:
            return access_error

        if lesson_id:
            # Get specific lesson by ID
            try:
                lesson_id = int(lesson_id)
                lesson = DailyAudioLesson.query.filter_by(
                    id=lesson_id, user_id=user.id
                ).first()
            except ValueError:
                return {
                    "error": "Invalid lesson_id parameter",
                    "status_code": 400
                }
        else:
            # Get most recent lesson for user
            lesson = (
                DailyAudioLesson.query.filter_by(user_id=user.id)
                .order_by(DailyAudioLesson.id.desc())
                .first()
            )

        if not lesson:
            return {
                "error": "No daily lesson found",
                "status_code": 404
            }

        return self._format_lesson_response(lesson)

    def get_todays_lesson_for_user(self, user):
        """
        Get today's daily audio lesson for a user.
        
        Args:
            user: The User object
            
        Returns:
            Dictionary with lesson details or message if no lesson today
        """
        # Check user access
        access_error = self._check_user_access(user)
        if access_error:
            return access_error

        # Get today's date range (start and end of today in UTC)
        today = date.today()
        start_of_today = datetime.combine(today, datetime.min.time())
        end_of_today = datetime.combine(today, datetime.max.time())

        # Find lesson created today
        lesson = (
            DailyAudioLesson.query.filter_by(user_id=user.id)
            .filter(DailyAudioLesson.created_at >= start_of_today)
            .filter(DailyAudioLesson.created_at <= end_of_today)
            .order_by(DailyAudioLesson.id.desc())
            .first()
        )

        if not lesson:
            return {"lesson": None, "message": "No lesson generated yet today"}

        return self._format_lesson_response(lesson)

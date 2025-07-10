"""
Daily lesson generator for creating audio lessons from user words.
"""

import os
import time
from datetime import datetime, date, timezone, timedelta

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
from zeeguu.logging import log, logp


class DailyLessonGenerator:
    """Generates daily audio lessons for users."""

    def __init__(self):
        self.voice_synthesizer = VoiceSynthesizer()
        self.lesson_builder = LessonBuilder()

    def generate_daily_lesson_for_user(self, user, timezone_offset=0):
        """
        Generate a daily audio lesson for a user with automatic word selection.
        This is the main entry point for generating lessons from the API.

        Args:
            user: The User object to generate a lesson for
            timezone_offset: Client's timezone offset in minutes from UTC

        Returns:
            Dictionary with lesson details or error information
        """
        logp(
            f"[generate_daily_lesson_for_user] Starting for user {user.id} ({user.name}), timezone_offset={timezone_offset}"
        )

        # Check if user has access to daily audio lessons
        if not user.has_feature("daily_audio"):
            logp(
                f"[generate_daily_lesson_for_user] User {user.id} does not have daily_audio feature"
            )
            return {
                "error": "Daily audio lessons are not available for your account",
                "status_code": 403,
            }

        # Check if a lesson already exists for today
        logp(f"[generate_daily_lesson_for_user] Checking for existing lesson today")
        existing_lesson = self.get_todays_lesson_for_user(user, timezone_offset)
        if existing_lesson.get("lesson_id"):
            # Return existing lesson instead of generating a new one
            logp(
                f"[generate_daily_lesson_for_user] Found existing lesson {existing_lesson.get('lesson_id')} for today"
            )
            return existing_lesson

        # Select words for the lesson
        logp(f"[generate_daily_lesson_for_user] Selecting words for lesson")
        selected_words = self.select_words_for_lesson(user, 3)
        logp(
            f"[generate_daily_lesson_for_user] Selected {len(selected_words)} words for lesson"
        )
        if len(selected_words) < 3:
            logp(
                f"[generate_daily_lesson_for_user] Not enough words: {len(selected_words)} < 3"
            )
            return {
                "error": f"Not enough new words to generate a lesson. Need at least 3 words.",
                "available_words": len(selected_words),
                "status_code": 400,
            }

        # Get user's languages and CEFR level
        origin_language = user.learned_language.code
        translation_language = user.native_language.code
        cefr_level = user.cefr_level_for_learned_language()
        logp(
            f"[generate_daily_lesson_for_user] User languages: {origin_language}->{translation_language}, CEFR: {cefr_level}"
        )

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
        logp(f"[select_words_for_lesson] Getting learning words for user {user.id}")
        # Get user's words that are currently being learned
        learning_words = BasicSRSchedule.user_words_to_study(user)
        if len(learning_words) < num_words:
            # append necessary words from user_words = BasicSRSchedule.scheduled_user_words(user)
            learning_words.extend(BasicSRSchedule.scheduled_user_words(user))

        logp(
            f"[select_words_for_lesson] Found {len(learning_words)} words in user's learning queue"
        )

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
                DailyAudioLesson.id == DailyAudioLessonSegment.daily_audio_lesson_id,
            )
            .filter(DailyAudioLesson.user_id == user.id)
            .distinct()
            .all()
        )

        existing_meaning_ids = {m[0] for m in meanings_already_in_lessons}
        logp(
            f"[select_words_for_lesson] Found {len(existing_meaning_ids)} meanings already used in lessons"
        )

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

        logp(
            f"[select_words_for_lesson] Available words after filtering: {len(available_words)}"
        )
        logp(
            f"[select_words_for_lesson] Selected {len(selected_words)} words: {[w.meaning.origin.content for w in selected_words]}"
        )

        return selected_words

    def generate_daily_lesson(
        self,
        user: User,
        selected_words: list,
        origin_language: str,
        translation_language: str,
        cefr_level: str,
    ) -> dict:
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
            logp(
                f"[generate_daily_lesson] Starting lesson generation for user {user.id} with {len(selected_words)} words"
            )

            # Create daily lesson
            daily_lesson = DailyAudioLesson(
                user=user,
                created_by="generate_daily_lesson_v1",
                language=user.learned_language,
            )
            db.session.add(daily_lesson)
            logp(f"[generate_daily_lesson] Created daily lesson object")

            # Generate audio lesson for each selected word
            for idx, user_word in enumerate(selected_words):
                meaning = user_word.meaning
                logp(
                    f"[generate_daily_lesson] Processing word {idx+1}/{len(selected_words)}: {meaning.origin.content}"
                )

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
                    logp(
                        f"[generate_daily_lesson] Failed to generate script for {meaning.origin.content}: {str(e)}"
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
                    logp(
                        f"[generate_daily_lesson] Failed to generate audio for {meaning.origin.content}: {str(e)}"
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
                logp(f"[generate_daily_lesson] Failed to build daily lesson: {str(e)}")
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
            logp(
                f"[generate_daily_lesson] Unexpected error in daily lesson generation: {str(e)}"
            )
            import traceback

            logp(f"[generate_daily_lesson] Traceback: {traceback.format_exc()}")
            return {"error": f"Unexpected error: {str(e)}"}

    def _check_user_access(self, user):
        """Check if user has access to daily audio lessons."""
        if not user.has_feature("daily_audio"):

            return {
                "error": "Daily audio lessons are not available for your account",
                "status_code": 403,
            }
        return None

    def _get_user_day_range_utc(self, timezone_offset=0):
        """
        Get the start and end of today in the user's timezone, converted to UTC.

        Args:
            timezone_offset: Client's timezone offset in minutes from UTC

        Returns:
            tuple: (start_of_today_utc, end_of_today_utc)
        """
        # Get today's date range in the user's timezone
        user_timezone = timezone(timedelta(minutes=timezone_offset))
        now_user = datetime.now(user_timezone)
        today_user = now_user.date()
        start_of_today_user = datetime.combine(today_user, datetime.min.time())
        end_of_today_user = datetime.combine(today_user, datetime.max.time())

        # Apply timezone offset to get UTC times
        start_of_today_utc = (
            start_of_today_user.replace(tzinfo=user_timezone)  # e.g. Jul 5, 01:00, CET
            .astimezone(timezone.utc)  # converts to Jul 4, 23:00, UTC
            .replace(
                tzinfo=None
            )  # keeps only JUl 4, 23:00 w/o the TZ info - useful for the DB
        )
        end_of_today_utc = (
            end_of_today_user.replace(tzinfo=user_timezone)
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )

        return start_of_today_utc, end_of_today_utc

    def _format_lesson_response(self, lesson):
        """Format a lesson into the standard response format."""
        # Check if audio file exists
        audio_path = os.path.join(
            ZEEGUU_DATA_FOLDER, "audio", "daily_lessons", f"{lesson.id}.mp3"
        )

        if not os.path.exists(audio_path):
            return {"error": "Audio file not found for this lesson", "status_code": 404}

        # Get lesson details including words
        words = []
        for segment in lesson.segments:
            if (
                segment.segment_type == "meaning_lesson"
                and segment.audio_lesson_meaning
            ):
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
            "pause_position_seconds": lesson.pause_position_seconds,
            "is_paused": lesson.is_paused,
            "is_completed": lesson.is_completed,
            "listened_count": lesson.listened_count,
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
                return {"error": "Invalid lesson_id parameter", "status_code": 400}
        else:
            # Get most recent lesson for user's current learned language
            lesson = (
                DailyAudioLesson.query.filter_by(
                    user_id=user.id, language_id=user.learned_language.id
                )
                .order_by(DailyAudioLesson.id.desc())
                .first()
            )

        if not lesson:
            return {"error": "No daily lesson found", "status_code": 404}

        return self._format_lesson_response(lesson)

    def get_todays_lesson_for_user(self, user, timezone_offset=0):
        """
        Get today's daily audio lesson for a user.

        Args:
            user: The User object
            timezone_offset: Client's timezone offset in minutes from UTC

        Returns:
            Dictionary with lesson details or message if no lesson today
        """
        # Check user access
        access_error = self._check_user_access(user)
        if access_error:
            return access_error

        # Get today's date range in UTC
        start_of_today_utc, end_of_today_utc = self._get_user_day_range_utc(
            timezone_offset
        )

        # Find lesson created today for the user's current learned language
        lesson = (
            DailyAudioLesson.query.filter_by(
                user_id=user.id, language_id=user.learned_language.id
            )
            .filter(DailyAudioLesson.created_at >= start_of_today_utc)
            .filter(DailyAudioLesson.created_at <= end_of_today_utc)
            .order_by(DailyAudioLesson.id.desc())
            .first()
        )

        if not lesson:
            return {"lesson": None, "message": "No lesson generated yet today"}

        return self._format_lesson_response(lesson)

    def delete_todays_lesson_for_user(self, user, timezone_offset=0):
        """
        Delete today's daily audio lesson for a user.

        Args:
            user: The User object
            timezone_offset: Client's timezone offset in minutes from UTC

        Returns:
            Dictionary with success message or error information
        """
        # Check user access
        access_error = self._check_user_access(user)
        if access_error:
            return access_error

        # Get today's date range in UTC
        start_of_today_utc, end_of_today_utc = self._get_user_day_range_utc(
            timezone_offset
        )

        # Find lesson created today for the user's current learned language
        lesson = (
            DailyAudioLesson.query.filter_by(
                user_id=user.id, language_id=user.learned_language.id
            )
            .filter(DailyAudioLesson.created_at >= start_of_today_utc)
            .filter(DailyAudioLesson.created_at <= end_of_today_utc)
            .order_by(DailyAudioLesson.id.desc())
            .first()
        )

        if not lesson:
            return {"message": "No lesson found for today to delete"}

        try:
            # Delete audio file if it exists
            audio_path = os.path.join(
                ZEEGUU_DATA_FOLDER, "audio", "daily_lessons", f"{lesson.id}.mp3"
            )
            if os.path.exists(audio_path):
                os.remove(audio_path)
                log(f"Deleted audio file: {audio_path}")

            # Delete the lesson from database (cascading deletes will handle segments)
            lesson_id = lesson.id
            db.session.delete(lesson)
            db.session.commit()

            log(f"Deleted today's lesson {lesson_id} for user {user.id}")
            return {
                "message": f"Today's lesson (ID: {lesson_id}) has been deleted successfully"
            }

        except Exception as e:
            db.session.rollback()
            log(f"Error deleting today's lesson for user {user.id}: {str(e)}")
            return {
                "error": f"Failed to delete today's lesson: {str(e)}",
                "status_code": 500,
            }

    def get_past_daily_lessons_for_user(
        self, user, limit=20, offset=0, timezone_offset=0
    ):
        """
        Get past daily audio lessons for a user with pagination.

        Args:
            user: The User object
            limit: Maximum number of lessons to return (default 20)
            offset: Number of lessons to skip (default 0)
            timezone_offset: Client's timezone offset in minutes from UTC

        Returns:
            Dictionary with lessons list and pagination info or error information
        """
        # Check user access
        access_error = self._check_user_access(user)
        if access_error:
            return access_error

        try:
            # Get today's start time in UTC to exclude today's lessons
            start_of_today_utc, _ = self._get_user_day_range_utc(timezone_offset)

            # Get total count of past lessons (excluding today) for pagination
            total_count = (
                DailyAudioLesson.query.filter_by(
                    user_id=user.id, language_id=user.learned_language.id
                )
                .filter(DailyAudioLesson.created_at < start_of_today_utc)
                .count()
            )

            # Get past lessons with pagination (excluding today)
            lessons = (
                DailyAudioLesson.query.filter_by(
                    user_id=user.id, language_id=user.learned_language.id
                )
                .filter(DailyAudioLesson.created_at < start_of_today_utc)
                .order_by(DailyAudioLesson.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            # Format each lesson
            lessons_data = []
            for lesson in lessons:
                # Check if audio file exists
                audio_path = os.path.join(
                    ZEEGUU_DATA_FOLDER, "audio", "daily_lessons", f"{lesson.id}.mp3"
                )
                audio_exists = os.path.exists(audio_path)

                # Get lesson words
                words = []
                for segment in lesson.segments:
                    if (
                        segment.segment_type == "meaning_lesson"
                        and segment.audio_lesson_meaning
                    ):
                        meaning = segment.audio_lesson_meaning.meaning
                        words.append(
                            {
                                "origin": meaning.origin.content,
                                "translation": meaning.translation.content,
                            }
                        )

                lessons_data.append(
                    {
                        "lesson_id": lesson.id,
                        "audio_url": (
                            f"/audio/daily_lessons/{lesson.id}.mp3"
                            if audio_exists
                            else None
                        ),
                        "audio_exists": audio_exists,
                        "duration_seconds": lesson.duration_seconds,
                        "created_at": (
                            lesson.created_at.isoformat() if lesson.created_at else None
                        ),
                        "completed_at": (
                            lesson.completed_at.isoformat()
                            if lesson.completed_at
                            else None
                        ),
                        "is_completed": lesson.is_completed,
                        "words": words,
                        "word_count": len(words),
                        "pause_position_seconds": lesson.pause_position_seconds,
                        "is_paused": lesson.is_paused,
                        "listened_count": lesson.listened_count,
                    }
                )

            return {
                "lessons": lessons_data,
                "pagination": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + limit < total_count,
                },
            }

        except Exception as e:
            log(f"Error fetching past lessons for user {user.id}: {str(e)}")
            return {
                "error": f"Failed to fetch past lessons: {str(e)}",
                "status_code": 500,
            }

    def update_lesson_state_for_user(self, user, lesson_id, state_data):
        """
        Update the state of a daily audio lesson for a user.

        Args:
            user: The User object
            lesson_id: ID of the lesson to update
            state_data: Dictionary containing state updates
                - action: 'play', 'pause', 'complete', 'resume'
                - position_seconds: Current playback position (for pause)

        Returns:
            Dictionary with success message or error information
        """
        # Check user access
        access_error = self._check_user_access(user)
        if access_error:
            return access_error

        try:
            # Find the lesson
            lesson = DailyAudioLesson.query.filter_by(
                id=lesson_id, user_id=user.id
            ).first()

            if not lesson:
                return {"error": "Lesson not found", "status_code": 404}

            action = state_data.get("action")
            position_seconds = state_data.get("position_seconds", 0)

            if action == "play":
                # Increment listen count when starting to play
                lesson.listened_count += 1

            elif action == "pause":
                # Record pause position and time
                lesson.pause_at(position_seconds)

            elif action == "resume":
                # Increment listen count when resuming
                lesson.resume()

            elif action == "complete":
                # Mark lesson as completed
                lesson.mark_completed()

            else:
                return {
                    "error": f"Invalid action: {action}. Must be 'play', 'pause', 'resume', or 'complete'",
                    "status_code": 400,
                }

            db.session.commit()

            return {
                "message": f"Lesson state updated successfully",
                "lesson_id": lesson.id,
                "action": action,
                "is_completed": lesson.is_completed,
                "is_paused": lesson.is_paused,
                "listened_count": lesson.listened_count,
                "pause_position_seconds": lesson.pause_position_seconds,
            }

        except Exception as e:
            db.session.rollback()
            log(
                f"Error updating lesson state for user {user.id}, lesson {lesson_id}: {str(e)}"
            )
            return {
                "error": f"Failed to update lesson state: {str(e)}",
                "status_code": 500,
            }

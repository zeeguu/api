"""
Bookmark update operations - extracted from translation.py for better maintainability.

This module handles the complex logic of updating bookmarks when users edit:
- The origin word
- The translation
- The context sentence

See docs/BOOKMARK_UPDATE_LOGIC.md for detailed documentation.
"""
from zeeguu.logging import log
from zeeguu.core.model import Meaning, Text, BookmarkContext, UserWord, Bookmark, Exercise
from zeeguu.core.model.bookmark_user_preference import UserWordExPreference
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord


def parse_update_params(request_json, bookmark):
    """
    Extract and sanitize update parameters from request.

    Args:
        request_json: Flask request.json dict
        bookmark: Original bookmark being updated

    Returns:
        dict with keys: word_str, translation_str, context_str,
                       context_identifier, context_type,
                       origin_lang_code, translation_lang_code
    """
    from urllib.parse import unquote_plus
    from string import punctuation

    punctuation_extended = "»«" + punctuation

    return {
        'word_str': unquote_plus(request_json["word"]).strip(punctuation_extended),
        'translation_str': request_json["translation"],
        'context_str': request_json.get("context", "").strip(),
        'context_identifier': request_json.get("context_identifier", None),
        'context_type': request_json.get("context_identifier", {}).get("context_type"),
        'origin_lang_code': bookmark.user_word.meaning.origin.language.code,
        'translation_lang_code': bookmark.user_word.meaning.translation.language.code,
    }


def find_or_create_meaning(db_session, word_str, origin_lang_code, translation_str, translation_lang_code):
    """
    Find or create Meaning for the new word/translation pair.

    Args:
        db_session: SQLAlchemy session
        word_str: Origin word
        origin_lang_code: Language code for origin word
        translation_str: Translation text
        translation_lang_code: Language code for translation

    Returns:
        Meaning object
    """
    meaning = Meaning.find_or_create(
        db_session,
        word_str,
        origin_lang_code,
        translation_str,
        translation_lang_code,
    )

    print(f"[UPDATE_BOOKMARK] Found/created Meaning {meaning.id}: '{word_str}' -> '{translation_str}'")
    return meaning


def find_or_create_context(db_session, context_str, context_type, bookmark):
    """
    Find or create Text and BookmarkContext for the new context.

    Preserves position information if context hasn't changed.

    Args:
        db_session: SQLAlchemy session
        context_str: New context sentence
        context_type: Type of context (e.g., 'ArticleFragment')
        bookmark: Original bookmark

    Returns:
        tuple: (Text, BookmarkContext)
    """
    prev_context = BookmarkContext.find_by_id(bookmark.context_id)
    prev_text = Text.find_by_id(bookmark.text_id)

    is_same_text = prev_text.content == context_str
    is_same_context = prev_context and prev_context.get_content() == context_str

    # Create Text (preserves metadata if same content)
    text = Text.find_or_create(
        db_session,
        context_str,
        bookmark.user_word.meaning.origin.language,
        bookmark.text.url,
        bookmark.text.article if is_same_text else None,
        prev_text.paragraph_i if is_same_text else None,
        prev_text.sentence_i if is_same_text else None,
        prev_text.token_i if is_same_text else None,
        prev_text.in_content if is_same_text else None,
        prev_text.left_ellipsis if is_same_text else None,
        prev_text.right_ellipsis if is_same_text else None,
    )

    # Create BookmarkContext (preserves position if same content)
    context = BookmarkContext.find_or_create(
        db_session,
        context_str,
        context_type,
        bookmark.user_word.meaning.origin.language,
        prev_context.sentence_i if is_same_context else None,
        prev_context.token_i if is_same_context else None,
        prev_context.left_ellipsis if is_same_context else None,
        prev_context.right_ellipsis if is_same_context else None,
    )

    print(f"[UPDATE_BOOKMARK] Found/created Text {text.id} and Context {context.id}")
    return text, context


def transfer_schedule(db_session, old_user_word, new_user_word):
    """
    Transfer spaced repetition schedule from old to new UserWord.

    Args:
        db_session: SQLAlchemy session
        old_user_word: Original UserWord
        new_user_word: New UserWord

    Returns:
        bool: True if schedule was transferred
    """
    print(f"[UPDATE_BOOKMARK] Looking for schedule for old UserWord {old_user_word.id}...")
    old_schedule = BasicSRSchedule.find_by_user_word(old_user_word)

    if not old_schedule:
        print(f"[UPDATE_BOOKMARK] No schedule found for old UserWord {old_user_word.id}")
        return False

    print(f"[UPDATE_BOOKMARK] Found old schedule (ID: {old_schedule.id}, next_practice: {old_schedule.next_practice_time})")

    # Check if new UserWord already has a schedule
    new_schedule = BasicSRSchedule.find_by_user_word(new_user_word)

    if not new_schedule:
        print(f"[UPDATE_BOOKMARK] Creating new schedule for UserWord {new_user_word.id}...")
        # Create new schedule with same state
        new_schedule = FourLevelsPerWord(user_word=new_user_word)
        new_schedule.next_practice_time = old_schedule.next_practice_time
        new_schedule.consecutive_correct_answers = old_schedule.consecutive_correct_answers
        new_schedule.cooling_interval = old_schedule.cooling_interval
        db_session.add(new_schedule)
        print(f"[UPDATE_BOOKMARK] ✓ Transferred schedule to UserWord {new_user_word.id}")
    else:
        print(f"[UPDATE_BOOKMARK] New UserWord already has schedule (ID: {new_schedule.id}), keeping existing")

    # Delete old schedule
    print(f"[UPDATE_BOOKMARK] Deleting old schedule {old_schedule.id}...")
    db_session.delete(old_schedule)
    print(f"[UPDATE_BOOKMARK] ✓ Deleted old schedule")

    return True


def transfer_exercises(db_session, old_user_word, new_user_word):
    """
    Transfer exercise history from old to new UserWord.

    Args:
        db_session: SQLAlchemy session
        old_user_word: Original UserWord
        new_user_word: New UserWord

    Returns:
        int: Number of exercises transferred
    """
    log(f"[UPDATE_BOOKMARK] Looking for exercises for old UserWord {old_user_word.id}...")
    old_exercises = Exercise.query.filter_by(user_word_id=old_user_word.id).all()

    if not old_exercises:
        log(f"[UPDATE_BOOKMARK] No exercises found for old UserWord {old_user_word.id}")
        return 0

    log(f"[UPDATE_BOOKMARK] Found {len(old_exercises)} exercises, transferring...")
    for ex in old_exercises:
        ex.user_word_id = new_user_word.id
        db_session.add(ex)

    log(f"[UPDATE_BOOKMARK] ✓ Transferred {len(old_exercises)} exercises to UserWord {new_user_word.id}")
    return len(old_exercises)


def preserve_learning_progress(db_session, old_user_word, new_user_word):
    """
    Preserve user's learning progress when switching UserWords.

    Transfers:
    - Level (spaced repetition level 0-3)
    - User preferences (if was studying, continue studying)

    Args:
        db_session: SQLAlchemy session
        old_user_word: Original UserWord
        new_user_word: New UserWord
    """
    old_fit_for_study = old_user_word.fit_for_study
    old_user_preference = old_user_word.user_preference
    old_level = old_user_word.level

    if not old_fit_for_study:
        print(f"[UPDATE_BOOKMARK] Old word was not fit for study, no progress to preserve")
        return

    # Transfer level
    print(f"[UPDATE_BOOKMARK] Preserving level {old_level} from old UserWord")
    new_user_word.level = old_level

    # If new word is unfit but user was studying old word, override with preference
    if not new_user_word.fit_for_study and old_user_preference != UserWordExPreference.DONT_USE_IN_EXERCISES:
        print(f"[UPDATE_BOOKMARK] Overriding fit_for_study with user preference (user was studying this)")
        new_user_word.user_preference = UserWordExPreference.USE_IN_EXERCISES
        new_user_word.update_fit_for_study(db_session)


def transfer_learning_progress(db_session, old_user_word, new_user_word, bookmark):
    """
    Transfer all learning data from old to new UserWord.

    Main orchestrator for transfer operations.

    Args:
        db_session: SQLAlchemy session
        old_user_word: Original UserWord
        new_user_word: New UserWord
        bookmark: Bookmark being updated
    """
    print(f"[UPDATE_BOOKMARK] UserWord changed from {old_user_word.id} to {new_user_word.id}, transferring data...")

    # Transfer schedule
    transfer_schedule(db_session, old_user_word, new_user_word)

    # Preserve learning progress (level, preferences)
    preserve_learning_progress(db_session, old_user_word, new_user_word)

    # Transfer exercises
    transfer_exercises(db_session, old_user_word, new_user_word)

    # Note: preferred_bookmark_id will be set after bookmark reassignment in main endpoint


def cleanup_old_user_word(db_session, old_user_word, moved_bookmark):
    """
    Clean up old UserWord after moving bookmark to new UserWord.

    Handles two cases:
    1. Old UserWord has no more bookmarks → delete it
    2. Old UserWord still has bookmarks → update preferred_bookmark

    Args:
        db_session: SQLAlchemy session
        old_user_word: Original UserWord that lost a bookmark
        moved_bookmark: Bookmark that was moved away
    """
    # Clear preferred_bookmark if it pointed to the moved bookmark
    if old_user_word.preferred_bookmark_id == moved_bookmark.id:
        log(f"[UPDATE_BOOKMARK] Clearing old UserWord's preferred_bookmark_id...")
        old_user_word.preferred_bookmark_id = None
        db_session.add(old_user_word)

    # Check how many bookmarks remain
    log(f"[UPDATE_BOOKMARK] Checking remaining bookmarks for old UserWord {old_user_word.id}...")
    remaining_bookmarks = Bookmark.query.filter_by(user_word_id=old_user_word.id).count()
    log(f"[UPDATE_BOOKMARK] Remaining bookmarks: {remaining_bookmarks}")

    if remaining_bookmarks == 0:
        # Delete orphaned UserWord
        log(f"[UPDATE_BOOKMARK] Deleting orphaned UserWord {old_user_word.id}...")
        db_session.delete(old_user_word)
        log(f"[UPDATE_BOOKMARK] ✓ Deleted orphaned UserWord {old_user_word.id}")
    elif remaining_bookmarks > 0 and old_user_word.preferred_bookmark_id is None:
        # Set new preferred bookmark
        log(f"[UPDATE_BOOKMARK] Setting new preferred bookmark for old UserWord {old_user_word.id}...")
        other_bookmarks = (
            Bookmark.query.filter_by(user_word_id=old_user_word.id)
            .order_by(Bookmark.id.asc())
            .all()
        )
        if other_bookmarks:
            old_user_word.preferred_bookmark_id = other_bookmarks[0].id
            db_session.add(old_user_word)
            log(f"[UPDATE_BOOKMARK] ✓ Updated preferred_bookmark to {other_bookmarks[0].id}")


def validate_and_update_position(bookmark, word_str, context_str):
    """
    Validate word appears in context and update position anchors.

    Args:
        bookmark: Bookmark to update
        word_str: Origin word to validate
        context_str: Context sentence

    Returns:
        dict: Error response if validation fails, None if success
    """
    from zeeguu.core.tokenization.word_position_finder import validate_single_occurrence
    from zeeguu.api.utils.json_result import json_result

    language = bookmark.user_word.meaning.origin.language

    print(f"[UPDATE_BOOKMARK] Validating word position in new context...")
    validation_result = validate_single_occurrence(word_str, context_str, language)

    if not validation_result["valid"]:
        log(f"ERROR: Word validation failed for '{word_str}' in context: {validation_result['error_type']}")

        # Return appropriate error response
        if validation_result["error_type"] == "multiple_occurrences":
            return json_result(
                {
                    "error": "Ambiguous word placement",
                    "detail": validation_result["error_message"],
                    "word": word_str,
                    "context": context_str,
                },
                status=400,
            )
        else:
            return json_result(
                {
                    "error": (
                        "Word not found in context"
                        if validation_result["error_type"] == "not_found"
                        else "Processing failed"
                    ),
                    "detail": validation_result["error_message"],
                    "word": word_str,
                    "context": context_str,
                },
                status=400,
            )

    # Update position anchors
    position_data = validation_result["position_data"]
    bookmark.sentence_i = position_data["sentence_i"]
    bookmark.token_i = position_data["token_i"]
    bookmark.total_tokens = position_data["total_tokens"]
    print(f"[UPDATE_BOOKMARK] ✓ Updated position: sentence_i={bookmark.sentence_i}, token_i={bookmark.token_i}")

    # Update context type if context changed
    prev_context = BookmarkContext.find_by_id(bookmark.context_id)
    if prev_context and prev_context.get_content() != context_str:
        from zeeguu.core.model.context_type import ContextType
        bookmark.context.context_type = ContextType.find_by_type(ContextType.USER_EDITED_TEXT)
        print(f"[UPDATE_BOOKMARK] ✓ Updated context type to USER_EDITED_TEXT")

    return None  # Success


def context_or_word_changed(word_str, context_str, bookmark, original_user_word, old_context_id=None, old_text_id=None):
    """
    Check if context or word has changed from original bookmark.

    Args:
        word_str: New origin word
        context_str: New context sentence
        bookmark: Original bookmark (may have been reassigned already)
        original_user_word: The UserWord before any updates (to compare against)
        old_context_id: Original context_id (if bookmark was already reassigned)
        old_text_id: Original text_id (if bookmark was already reassigned)

    Returns:
        bool: True if context or word changed
    """
    # Use provided IDs if available (bookmark may have been reassigned already)
    prev_context = BookmarkContext.find_by_id(old_context_id or bookmark.context_id)
    prev_text = Text.find_by_id(old_text_id or bookmark.text_id)

    is_same_text = prev_text.content == context_str
    is_same_context = prev_context and prev_context.get_content() == context_str
    is_same_word = original_user_word.meaning.origin.content == word_str

    # Return True if ANY of these changed (word OR context)
    word_changed = not is_same_word
    context_changed = not is_same_text or not is_same_context

    print(f"[UPDATE_BOOKMARK] context_or_word_changed check:")
    print(f"  original_word: '{original_user_word.meaning.origin.content}' -> new_word: '{word_str}'")
    print(f"  is_same_word: {is_same_word}, word_changed: {word_changed}")
    print(f"  is_same_context: {is_same_context}, context_changed: {context_changed}")
    print(f"  result: {word_changed or context_changed}")

    return word_changed or context_changed


def format_response(bookmark, new_user_word):
    """
    Format updated bookmark as JSON response.

    Args:
        bookmark: Updated bookmark
        new_user_word: UserWord bookmark now belongs to

    Returns:
        Flask response with JSON
    """
    from zeeguu.api.utils.json_result import json_result

    updated_bookmark = bookmark.as_dictionary(
        with_exercise_info=True,
        with_context_tokenized=True,
        with_context=True
    )

    # Add warning if word won't appear in study list
    if not new_user_word.fit_for_study:
        updated_bookmark["_message"] = (
            "This word may not appear in your study list due to quality filters. "
            "You can still find it in the article where you saved it."
        )
        log(f"[UPDATE_BOOKMARK] ⚠️  UserWord {new_user_word.id} is not fit for study")

    print(f"[UPDATE_BOOKMARK] ✓ Update completed successfully for bookmark {bookmark.id}")
    print(f"[UPDATE_BOOKMARK] Returning: word='{updated_bookmark.get('from')}', translation='{updated_bookmark.get('to')}'")

    return json_result(updated_bookmark)

from zeeguu.core.model.exercise_outcome import ExerciseOutcome
from zeeguu.core.model.user_word import UserWord
from zeeguu.core.verbal_flashcards.flashcard_selection import (
    ensure_schedule_for_verbal_flashcard,
    find_flashcard_for_user,
)
from zeeguu.core.verbal_flashcards.fuzzy_match import calculate_accuracy


VERBAL_FLASHCARD_EXERCISE_SOURCE = "Verbal Flashcards"


def record_flashcard_answer(
    db_session,
    user,
    flashcard_id,
    user_answer,
    is_correct,
    answer_source,
    response_time,
    session_id,
    language_code=None,
):
    flashcard = find_flashcard_for_user(user, flashcard_id)
    if not flashcard:
        return None

    accuracy_analysis = None
    if user_answer:
        expected_text = flashcard["expectedText"]
        accuracy_analysis = calculate_accuracy(
            user_answer,
            expected_text,
            language_code=language_code,
        )

        if accuracy_analysis.get("isAccepted"):
            is_correct = True

    exercise_outcome = ExerciseOutcome.CORRECT if is_correct else ExerciseOutcome.WRONG
    other_feedback = f"answer_source={answer_source}"
    flashcard_user_word_id = flashcard["user_word_id"]

    user_word = UserWord.query.get(flashcard_user_word_id)
    if not user_word or user_word.user_id != user.id:
        return None

    ensure_schedule_for_verbal_flashcard(db_session, user_word)

    user_word.report_exercise_outcome(
        db_session,
        VERBAL_FLASHCARD_EXERCISE_SOURCE,
        exercise_outcome,
        response_time,
        session_id,
        other_feedback,
    )

    response_data = {
        "success": True,
        "flashcard_id": flashcard_id,
        "is_correct": is_correct,
        "exercise_outcome": exercise_outcome,
        "message": "Answer recorded",
    }

    if accuracy_analysis:
        response_data["accuracy_analysis"] = accuracy_analysis

    return response_data

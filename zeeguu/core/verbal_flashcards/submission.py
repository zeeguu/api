from zeeguu.core.model.exercise_outcome import ExerciseOutcome
from zeeguu.core.verbal_flashcards.flashcard_selection import (
    answer_variants_for_bookmark,
    find_flashcard_submission_target,
)
from zeeguu.core.verbal_flashcards.fuzzy_match import calculate_accuracy_against_variants


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
    bookmark = find_flashcard_submission_target(user, flashcard_id)
    if not bookmark:
        return None

    user_word = bookmark.user_word

    accuracy_analysis = None
    if user_answer:
        expected_texts = answer_variants_for_bookmark(bookmark)
        accuracy_analysis = calculate_accuracy_against_variants(
            user_answer,
            expected_texts,
            language_code=language_code,
        )

        if accuracy_analysis.get("isAccepted"):
            is_correct = True

    exercise_outcome = ExerciseOutcome.CORRECT if is_correct else ExerciseOutcome.WRONG
    other_feedback = f"answer_source={answer_source}"

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

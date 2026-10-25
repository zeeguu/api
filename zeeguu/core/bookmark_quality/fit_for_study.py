from zeeguu.core.bookmark_quality import bad_quality_reason
from zeeguu.core.model.study_choice import StudyChoice, UnfitReason


def unfit_reason(user_word):
    """
    Why the word can't be studied now, or None. A sticky verdict stays;
    anything else is worked out again from the word, which also clears a
    reason that only holds until the word is judged again (UnfitReason).
    """
    if user_word.unfit_reason in UnfitReason.STICKY:
        return user_word.unfit_reason

    # Separated MWEs (multi-word expressions with words between parts) are not fit for study
    # because fill-in-the-blank exercises don't work well with non-adjacent words
    if _is_separated_mwe(user_word):
        return UnfitReason.SEPARATED_MWE

    return bad_quality_reason(user_word)


def fit_given(study_choice, reason):
    """The learner's choice, then the system's reason: a STUDY choice lifts
    only the quality heuristics."""
    if study_choice in (StudyChoice.SKIP, StudyChoice.KNOWN):
        return False
    if reason is None:
        return True
    return reason in UnfitReason.LIFTABLE and study_choice == StudyChoice.STUDY


def fit_for_study(user_word):
    return fit_given(user_word.study_choice, unfit_reason(user_word))


def _is_separated_mwe(user_word):
    """Check if the user_word's preferred bookmark is a separated MWE."""
    if user_word.preferred_bookmark is None:
        return False
    return user_word.preferred_bookmark.mwe_partner_token_i is not None

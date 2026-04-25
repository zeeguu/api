"""
Feature toggle logic for users.

This module contains the core logic for determining which features
are enabled for a user based on their cohort membership, invitation code, etc.
"""

import os


def _csv_env_values(env_var_name):
    raw_value = os.environ.get(env_var_name, "")
    return {
        token.strip().casefold()
        for token in raw_value.split(",")
        if token.strip()
    }


def _feature_map():
    return {
        "audio_exercises": _audio_exercises,
        "daily_audio": _daily_audio,
        "extension_experiment_1": _extension_experiment_1,
        "no_audio_exercises": _no_audio_exercises,
        "tiago_exercises": _tiago_exercises,
        "new_topics": _new_topics,
        "daily_feedback": _daily_feedback,
        "hide_recommendations": _hide_recommendations,
        "verbal_flashcards": _verbal_flashcards,
        "show_non_simplified_articles": _show_non_simplified_articles,
        "always_open_externally": _always_open_externally,
        "gamification": _gamification
    }


def features_for_user(user):
    """Return list of feature names enabled for the given user."""
    features = []
    for name, detector_function in _feature_map().items():
        if detector_function(user):
            features.append(name)
    return features


def _daily_feedback(user):
    return user.is_member_of_cohort(565)


def is_feature_enabled_for_user(feature_name, user):
    """Check if a specific feature is enabled for the given user."""
    return feature_name in features_for_user(user)


def _daily_audio(user):
    # Enabled for everyone - kept for backward compatibility with deployed apps
    return True


def _new_topics(user):
    return True


def _tiago_exercises(user):
    right_user = user.invitation_code == "Tiago" or user.id == 534 or user.id == 4022
    right_language = user.learned_language.code in ["da"]
    return right_user and right_language


def _no_audio_exercises(user):
    return user.is_member_of_cohort(447)


def _audio_exercises(user):
    return user.is_member_of_cohort(444)


def _extension_experiment_1(user):
    return (
        (user.is_member_of_cohort(437))
        or user.id in [3372, 3373, 2953, 3427, 2705]
        or user.id > 3555
    )


def _show_non_simplified_articles(user):
    """Show non-simplified (original) articles.

    Transitional allowlist: the product direction is flipping so that
    full articles (opened externally) become the default. This set holds
    the pilots on the new flow while we validate it; eventually this will
    be the behavior for everyone and the flag can go away.
    """
    LEGACY_USER_IDS = {4607, 4626, 6083, 6250}
    return user.id in LEGACY_USER_IDS


def _always_open_externally(user):
    """Article cards in the feed always render the "Open Externally"
    button for these users — except for saved articles, which still
    open in the Zeeguu reader.

    Click-through behavior is unchanged: the redirect-notification modal
    still appears unless the user has dismissed it with "don't show again".

    Rollout: the original pilot users, plus every user signed up from id
    6367 onwards (i.e., all new users going forward). Existing users keep
    the in-reader flow until we flip the default for them too.
    """
    BETA_USER_IDS = {4607, 6083, 6250}
    NEW_USER_THRESHOLD = 6367
    return user.id in BETA_USER_IDS or user.id >= NEW_USER_THRESHOLD


def _hide_recommendations(user):
    """Hide recommended articles for students in specific cohorts.

    When enabled, students only see the Classroom tab with teacher-uploaded texts.
    Teachers are excluded from this feature even if they are in the cohort.
    """
    if user.isTeacher():
        return False

    COHORTS_WITH_HIDDEN_RECOMMENDATIONS = {564}

    for user_cohort in user.cohorts:
        if user_cohort.cohort_id in COHORTS_WITH_HIDDEN_RECOMMENDATIONS:
            return True
    return False


def _verbal_flashcards(user):
    """
    Enable verbal flashcards only for users whose own stored invitation code
    is explicitly allow-listed.
    """
    allowed_invite_codes = _csv_env_values("VERBAL_FLASHCARDS_INVITE_CODES")
    if not allowed_invite_codes:
        return False

    invitation_code = (getattr(user, "invitation_code", None) or "").strip().casefold()
    return invitation_code in allowed_invite_codes
  
# Gamification feature flag logic
from sqlalchemy.exc import NoResultFound

from .model.user import User
from .model.cohort import Cohort
def _gamification(user: User):
    """
    Enable general gamification features for users whose invitation with the gamification invite code,
    or who are in the gamification cohort. This includes features like badges, friends, and leaderboards.
    """

    GAMIFICATION_INVITE_CODE = "CD8HGKKJ"
    if user.is_dev:
        return True

    # Invitation code can be None
    invitation_code = user.invitation_code or ""
    if invitation_code.lower() == GAMIFICATION_INVITE_CODE.lower():
        return True

    # Find gamification cohort by invite code, if it exists.
    try:
        gamification_cohort = Cohort.find_by_code(GAMIFICATION_INVITE_CODE)
    except NoResultFound:
        gamification_cohort = None

    if gamification_cohort and user.is_member_of_cohort(gamification_cohort.id):
        return True

    # Disabled for everyone else
    return False

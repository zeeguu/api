"""
Feature toggle logic for users.

This module contains the core logic for determining which features
are enabled for a user based on their cohort membership, invitation code, etc.
"""


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
        "show_non_simplified_articles": _show_non_simplified_articles,
        "gamification": _gamification,
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
    """Show non-simplified (original) articles for legacy users.

    Most users only see simplified articles. These legacy users
    were active before simplification was standard and still expect
    to see original articles in their feed.
    """
    LEGACY_USER_IDS = {4607, 4626}
    return user.id in LEGACY_USER_IDS


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

# Gamification feature flag logic
from .model.user import User 
def _gamification(user: User):
    """
    Enable gamification features for users whose invitation code is exactly 'gamification'.
    """
    from datetime import datetime, date 
    GAMIFICATION_INVITE_CODE = "gamification" # I guess we can decide on the invitation code
    GAMIFICATION_START_DATE = date(2026, 4, 1) # Start after the first of April 2026
    
    # Start gamification features after the GAMIFICATION_START_DATE
    if datetime.now().date() > GAMIFICATION_START_DATE:
        return False
    
    return user.invitation_code == GAMIFICATION_INVITE_CODE 


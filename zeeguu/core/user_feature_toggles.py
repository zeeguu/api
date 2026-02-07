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
    }


def features_for_user(user):
    """Return list of feature names enabled for the given user."""
    features = []
    for name, detector_function in _feature_map().items():
        if detector_function(user):
            features.append(name)
    return features


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

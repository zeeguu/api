"""
Feature toggle logic for users.

This module contains the core logic for determining which features
are enabled for a user based on their cohort membership, invitation code, etc.
"""

import os
from sqlalchemy.exc import NoResultFound

from .model.cohort import Cohort
from .model.user import User


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
        "classroom_only": _classroom_only,
        # Legacy name for classroom_only, kept as of 25 Aug 2026. The native
        # apps ship a bundled web build, so a student whose app predates the
        # release that adopts the new name reads this string and nothing else.
        # Safe to delete once no app build from before 25 Aug 2026 is still in
        # use -- check the oldest active version first.
        "hide_recommendations": _classroom_only,
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
    # Guarded: features_for_user runs on every /user_details, so an account
    # without a learned language would take the whole call down. No such
    # account exists today, but the model allows one and the classroom code
    # already handles it.
    right_language = (
        user.learned_language is not None and user.learned_language.code in ["da"]
    )
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
    """Show non-simplified (original) articles in the feed.

    Now on for everyone: simplification has moved on-demand, so the crawl no
    longer pre-generates simplified children and the feed is originals-first for
    all users (a level-matched simplified version is created lazily when a learner
    opens an article). Previously a transitional allowlist ({4607, 4626, 6083,
    6250}); the rollout is complete, so this is the default.
    """
    return True


def _always_open_externally(user):
    """Article cards in the feed always render the "Open Externally" button
    (except saved articles, which still open in the Zeeguu reader).

    Click-through behavior is unchanged: the redirect-notification modal still
    appears unless the user dismissed it with "don't show again".

    Now on for everyone as part of the on-demand simplification flip. Previously
    a staged rollout (pilot users {4607, 6083, 6250}, new signups from id 6367,
    and all dev accounts); the rollout is complete, so this is the default.
    """
    return True


def _classroom_only(user):
    """The student sees only the texts their teacher shares with the class.

    Set per class by the teacher (Cohort.only_classroom_texts). A student in
    several classes is restricted if any one of them asks for it: the strictest
    class wins, and the way out is to leave that class.

    Teachers are excluded even when they are members of such a cohort -- they
    need the feed and search to find the texts they are going to share.
    """
    if user.isTeacher():
        return False

    cohort_ids = [user_cohort.cohort_id for user_cohort in user.cohorts]
    if not cohort_ids:
        return False

    return (
        Cohort.query.filter(Cohort.id.in_(cohort_ids))
        .filter(Cohort.only_classroom_texts.is_(True))
        .count()
        > 0
    )


def _verbal_flashcards(user):
    """
    Enable verbal flashcards for users invited with the dedicated verbal
    flashcards invite code, or who belong to the cohort associated with
    that code.
    """
    VERBAL_FLASHCARDS_INVITE_CODE = "spring2026"
    learned_language = getattr(user, "learned_language", None)
    learned_language_code = str(getattr(learned_language, "code", "") or "").casefold()
    if learned_language_code != "da":
        return False

    if user.is_dev:
        return True

    invitation_code = (user.invitation_code or "").strip()
    if invitation_code.lower() == VERBAL_FLASHCARDS_INVITE_CODE.lower():
        return True

    try:
        verbal_flashcards_cohort = Cohort.find_by_code(VERBAL_FLASHCARDS_INVITE_CODE)
    except NoResultFound:
        verbal_flashcards_cohort = None

    if verbal_flashcards_cohort and user.is_member_of_cohort(verbal_flashcards_cohort.id):
        return True

    return False


def _gamification(user: User):
    """
    Enable general gamification features (badges, friends, leaderboards) for
    everyone.

    Previously this was a staged rollout gated on the "CD8HGKKJ" invite code /
    cohort, dev accounts, and users with id > 6479. The rollout is complete, so
    the feature is now on for all users.
    """
    return True

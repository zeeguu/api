from sqlalchemy import func, and_, case, or_, literal

from zeeguu.core.model import User
from zeeguu.core.model.db import db
from zeeguu.core.model.friend import Friend
from zeeguu.core.model.user_avatar import UserAvatar


def exercise_time_leaderboard(
        user_ids_subquery,
        limit: int = 20,
        from_date=None,
        to_date=None,
):
    """
    Return leaderboard rows for current user and all friends ordered by total
    exercise session duration in descending order.
    """
    from zeeguu.core.model.user_exercise_session import UserExerciseSession

    total_duration = func.coalesce(func.sum(UserExerciseSession.duration), 0)

    joins = [
        (
            UserExerciseSession,
            and_(
                UserExerciseSession.user_id == User.id,
                *([UserExerciseSession.start_time >= from_date] if from_date else []),
                *([UserExerciseSession.start_time <= to_date] if to_date else []),
            )
        )
    ]

    return _leaderboard_base(
        user_ids_subquery,
        total_duration,
        joins,
        limit,
    )


def listening_time_leaderboard(
        user_ids_subquery,
        limit: int = 20,
        from_date=None,
        to_date=None,
):
    """
    Return leaderboard rows for current user and all friends ordered by total
    listening session duration in descending order.
    """
    from zeeguu.core.model.user_listening_session import UserListeningSession

    total_duration = func.coalesce(func.sum(UserListeningSession.duration), 0)

    joins = [
        (
            UserListeningSession,
            and_(
                UserListeningSession.user_id == User.id,
                *([UserListeningSession.start_time >= from_date] if from_date else []),
                *([UserListeningSession.start_time <= to_date] if to_date else []),
            )
        )
    ]

    return _leaderboard_base(
        user_ids_subquery,
        total_duration,
        joins,
        limit,
    )


def read_articles_leaderboard(
        user_ids_subquery,
        limit: int = 20,
        from_date=None,
        to_date=None,
):
    """
    Return leaderboard rows for current user and all friends ordered by
    number of completed articles in descending order.
    """
    from zeeguu.core.model.user_article import UserArticle

    completed_articles_count = func.count(UserArticle.id)

    joins = [
        (
            UserArticle,
            and_(
                UserArticle.user_id == User.id,
                UserArticle.completed_at.isnot(None),
                *([UserArticle.completed_at >= from_date] if from_date else []),
                *([UserArticle.completed_at <= to_date] if to_date else []),
            )
        )
    ]

    return _leaderboard_base(
        user_ids_subquery,
        completed_articles_count,
        joins,
        limit,
    )


def reading_time_leaderboard(
        user_ids_subquery,
        limit: int = 20,
        from_date=None,
        to_date=None,
):
    """
    Return leaderboard rows for current user and all friends ordered by total
    reading session duration in descending order.
    """
    from zeeguu.core.model.user_reading_session import UserReadingSession

    total_duration = func.coalesce(func.sum(UserReadingSession.duration), 0)

    joins = [
        (
            UserReadingSession,
            and_(
                UserReadingSession.user_id == User.id,
                *([UserReadingSession.start_time >= from_date] if from_date else []),
                *([UserReadingSession.start_time <= to_date] if to_date else []),
            )
        )
    ]

    return _leaderboard_base(
        user_ids_subquery,
        total_duration,
        joins,
        limit,
    )


def exercises_done_leaderboard(
        user_ids_subquery,
        limit: int = 20,
        from_date=None,
        to_date=None,
):
    """
    Return leaderboard rows for current user and all friends ordered by
    number of exercises done in descending order.
    """
    from zeeguu.core.model.exercise import Exercise
    from zeeguu.core.model.exercise_outcome import ExerciseOutcome
    from zeeguu.core.model.user_word import UserWord

    correct_exercise_outcomes = [
        ExerciseOutcome.CORRECT,
        ExerciseOutcome.CORRECT_AFTER_HINT,
        *ExerciseOutcome.correct_after_translation
    ]

    exercises_done_count = func.coalesce(
        func.sum(
            case(
                (
                    Exercise.outcome.has(ExerciseOutcome.outcome.in_(correct_exercise_outcomes)), 1), else_=0)), 0
    )

    joins = [
        (UserWord, UserWord.user_id == User.id),
        (
            Exercise,
            and_(
                Exercise.user_word_id == UserWord.id,
                *([Exercise.time >= from_date] if from_date else []),
                *([Exercise.time <= to_date] if to_date else [])
            )
        ),
        (
            ExerciseOutcome,
            ExerciseOutcome.id == Exercise.outcome_id
        ),
    ]

    return _leaderboard_base(
        user_ids_subquery,
        exercises_done_count,
        joins,
        limit,
    )


def friend_leaderboard_user_ids_subquery(user_id: int):
    # For each friendship row touching this user, select "the other user".
    return (
        db.session.query(
            case(
                (Friend.user_id == user_id, Friend.friend_id),
                else_=Friend.user_id,
            ).label("user_id")
        )
        .filter(or_(Friend.user_id == user_id, Friend.friend_id == user_id))
        .union(
            db.session.query(literal(user_id).label("user_id"))
        )
        .subquery()
    )

def cohort_leaderboard_user_ids_subquery(cohort_id: int):
    from zeeguu.core.model.user_cohort_map import UserCohortMap

    return (
        db.session.query(UserCohortMap.user_id.label("user_id"))
        .filter(UserCohortMap.cohort_id == cohort_id)
        .subquery()
    )


def _leaderboard_base(
        user_ids_subquery,
        value_expr,
        joins,
        limit
):
    # Base query selecting the users and their avatars
    query = (
        db.session.query(
            User.id.label("user_id"),
            User.name,
            User.username,
            UserAvatar.image_name,
            UserAvatar.character_color,
            UserAvatar.background_color,
            value_expr.label("value"),
        )
        .select_from(user_ids_subquery)
        .join(User, User.id == user_ids_subquery.c.user_id)
        .outerjoin(UserAvatar, UserAvatar.user_id == User.id)
    )

    # Adding other joined tables
    for model, condition in joins:
        query = query.outerjoin(model, condition)

    # Group by, ordering and limiting
    query = query.group_by(
        User.id,
        User.name,
        User.username,
        UserAvatar.image_name,
        UserAvatar.character_color,
        UserAvatar.background_color,
    ).order_by(value_expr.desc(), User.id.asc())

    if limit:
        query = query.limit(limit)

    return query.all()

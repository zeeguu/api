from datetime import datetime, timedelta

from sqlalchemy.orm import object_session

from zeeguu.core.model import Friendship
from zeeguu.core.model.db import db


def compute_current_streak(friendship: Friendship):
    """Stored friend streak, zeroed out if not updated today or yesterday."""
    last_updated = friendship.friend_streak_last_updated.date() if friendship.friend_streak_last_updated else None
    yesterday = datetime.now().date() - timedelta(days=1)

    if last_updated is None:
        return 0

    if last_updated < yesterday:
        return 0

    return friendship.friend_streak or 0


def update_streak(friendship: Friendship, session=None, commit=True):
    """
    Update friend_streak based on both users' most recent practice in any language.
    Uses the latest last_practiced date across all UserLanguage records for each user.
    Dates are evaluated in each user's local timezone so streaks are fair worldwide.
    """
    from zeeguu.core.util.time import user_local_today, to_user_local_date

    session = session or object_session(friendship) or db.session

    # Find last practice time for user_a and user_b across all languages
    user_a_last_practiced = friendship.user_a.last_practiced
    user_b_last_practiced = friendship.user_b.last_practiced

    # Convert each practice timestamp to the respective user's local date so that
    # a user who practices at 11 pm in their timezone is credited for that day,
    # not the server's day (which may already have rolled over).
    user_a_date = to_user_local_date(friendship.user_a, user_a_last_practiced)
    user_b_date = to_user_local_date(friendship.user_b, user_b_last_practiced)
    user_a_today = user_local_today(friendship.user_a)
    user_b_today = user_local_today(friendship.user_b)

    # last_updated is a server-side timestamp; keep it in server time for the
    # idempotency check (already_counted_today / streak_was_active_yesterday).
    server_today = datetime.now().date()
    server_yesterday = server_today - timedelta(days=1)
    last_updated_date = friendship.friend_streak_last_updated.date() if friendship.friend_streak_last_updated else None

    # Determine if the streak should be incremented, reset, or left unchanged:
    both_practiced_today = user_a_date == user_a_today and user_b_date == user_b_today
    either_has_no_history = user_a_date is None or user_b_date is None
    either_lapsed = _either_lapsed(user_a_date, user_b_date, user_a_today, user_b_today)
    already_counted_today = last_updated_date == server_today
    streak_was_active_yesterday = last_updated_date == server_yesterday and friendship.friend_streak > 0

    if either_has_no_history:
        pass  # do not reset if one side has never practiced
    elif both_practiced_today and not already_counted_today:
        if streak_was_active_yesterday:
            friendship.friend_streak += 1
        else:
            friendship.friend_streak = 1
        friendship.friend_streak_last_updated = datetime.now()
    elif either_lapsed:
        friendship.friend_streak = 0
        friendship.friend_streak_last_updated = datetime.now()

    if session:
        session.add(friendship)
        if commit:
            session.commit()


def _either_lapsed(user_a_date, user_b_date, user_a_today, user_b_today):
    """
    Return True only when both users have practice history and at least one hasn't
    practiced since before yesterday (in their own timezone).
    """
    if user_a_date is None or user_b_date is None:
        return False
    return user_a_date < user_a_today - timedelta(days=1) or user_b_date < user_b_today - timedelta(days=1)

#!/usr/bin/env python
"""
Migration script to populate daily_streak for existing users.

Calculates each user's current streak by finding consecutive days of activity
counting backward from their last_seen date.

Usage:
    source ~/.venvs/z_env/bin/activate && python -m tools.migrate_daily_streak [--dry-run] [--quiet]

Options:
    --dry-run    Show what would be updated without making changes
    --quiet, -q  Suppress per-user output (only show summary)
"""
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model.user import User
from zeeguu.core.model.user_activitiy_data import UserActivityData
from sqlalchemy import func


def get_active_days_for_user(user_id, lookback_days=365):
    """
    Returns a set of dates (as date objects) when the user had activity.
    """
    cutoff = datetime.now() - timedelta(days=lookback_days)

    # Get distinct dates of activity
    results = (
        db.session.query(func.date(UserActivityData.time))
        .filter(UserActivityData.user_id == user_id)
        .filter(UserActivityData.time > cutoff)
        .distinct()
        .all()
    )

    return {row[0] for row in results if row[0]}


def calculate_streak_from_dates(active_dates, reference_date=None):
    """
    Calculate streak by counting consecutive days backward from reference_date.

    This calculates what the user's streak WAS on their last visit,
    so when they return, the update_last_seen_if_needed logic can
    correctly increment or reset it.
    """
    if not active_dates:
        return 0

    if reference_date is None:
        reference_date = datetime.now().date()

    # Start counting from reference_date
    if reference_date not in active_dates:
        # Reference date has no activity - find most recent activity
        sorted_dates = sorted(active_dates, reverse=True)
        if sorted_dates:
            reference_date = sorted_dates[0]
        else:
            return 0

    streak = 0
    current = reference_date
    while current in active_dates:
        streak += 1
        current = current - timedelta(days=1)

    return streak


def migrate_streaks(dry_run=False, verbose=True):
    """
    Calculate and set daily_streak for all users with last_seen data.
    """
    from collections import Counter

    # Get all users who have been active (have last_seen set)
    users_with_activity = (
        User.query
        .filter(User.last_seen.isnot(None))
        .all()
    )

    print(f"Found {len(users_with_activity)} users with last_seen data")

    updated = 0
    skipped = 0
    streak_counts = Counter()

    for user in users_with_activity:
        # Get this user's active days
        active_days = get_active_days_for_user(user.id)

        if not active_days:
            # No activity data, use last_seen as single activity day
            if user.last_seen:
                active_days = {user.last_seen.date()}

        # Calculate streak from their last_seen date
        reference_date = user.last_seen.date() if user.last_seen else None
        streak = calculate_streak_from_dates(active_days, reference_date)
        streak_counts[streak] += 1

        # Update user
        old_streak = user.daily_streak or 0

        if streak != old_streak:
            if dry_run and verbose:
                print(f"  [DRY-RUN] User {user.id} ({user.email[:30]}...): {old_streak} -> {streak}")
            if not dry_run:
                user.daily_streak = streak
            updated += 1
        else:
            skipped += 1

    if not dry_run:
        db.session.commit()
        print(f"\nUpdated {updated} users, {skipped} already correct")
    else:
        print(f"\n[DRY-RUN] Would update {updated} users, {skipped} already correct")

    # Print streak distribution
    print("\nStreak distribution:")
    for streak_len in sorted(streak_counts.keys()):
        print(f"  {streak_len} days: {streak_counts[streak_len]} users")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    quiet = "--quiet" in sys.argv or "-q" in sys.argv

    if dry_run:
        print("Running in DRY-RUN mode (no changes will be made)\n")

    migrate_streaks(dry_run=dry_run, verbose=not quiet)

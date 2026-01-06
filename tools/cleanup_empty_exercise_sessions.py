#!/usr/bin/env python
"""
Cleanup script to delete exercise sessions that have zero exercises.
These empty sessions pollute activity tracking and statistics.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model.user_exercise_session import UserExerciseSession
from zeeguu.core.sql.learner.exercises_history import exercises_in_session


def find_empty_sessions():
    """Find all exercise sessions with zero exercises."""
    all_sessions = UserExerciseSession.query.all()
    empty_sessions = []

    for session in all_sessions:
        exercises = exercises_in_session(session.id)
        if not exercises:
            empty_sessions.append(session)

    return empty_sessions


def cleanup_empty_sessions(dry_run=True):
    """Delete exercise sessions with zero exercises."""
    empty_sessions = find_empty_sessions()

    print(f"Found {len(empty_sessions)} empty exercise sessions")

    if dry_run:
        print("\nDry run - showing first 20 empty sessions:")
        for session in empty_sessions[:20]:
            user = session.user
            duration_sec = session.duration / 1000 if session.duration else 0
            print(
                f"  Session {session.id}: user={user.name} ({user.id}), "
                f"date={session.start_time}, duration={duration_sec:.0f}s"
            )
        if len(empty_sessions) > 20:
            print(f"  ... and {len(empty_sessions) - 20} more")
        print("\nRun with --delete to remove these sessions")
    else:
        for session in empty_sessions:
            db.session.delete(session)
        db.session.commit()
        print(f"Deleted {len(empty_sessions)} empty sessions")


if __name__ == "__main__":
    dry_run = "--delete" not in sys.argv
    cleanup_empty_sessions(dry_run=dry_run)

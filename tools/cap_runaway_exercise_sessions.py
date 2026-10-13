#!/usr/bin/env python
"""
Lower the stored time of exercise sessions whose clock kept running long
after their last answer (a page left open, something resting on a key): to
the last answer plus UserExerciseSession.TIME_AFTER_LAST_ANSWER_MS, as the
server now does for every update. Lists them first; --apply writes.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from sqlalchemy import func

from zeeguu.core.model.exercise import Exercise
from zeeguu.core.model.user_exercise_session import UserExerciseSession

# Leave sessions alone unless the correction is at least this much.
MIN_CORRECTION_MS = 5 * 60 * 1000


def runaway_sessions():
    """(session, capped duration) for every session the cap would lower by
    MIN_CORRECTION_MS or more."""
    last_answers = (
        db.session.query(Exercise.session_id, func.max(Exercise.time))
        .filter(Exercise.session_id.isnot(None))
        .group_by(Exercise.session_id)
        .all()
    )
    sessions = {
        s.id: s
        for s in UserExerciseSession.query.filter(
            UserExerciseSession.id.in_([sid for sid, _ in last_answers])
        )
    }
    result = []
    for session_id, last_answer in last_answers:
        session = sessions.get(session_id)
        if not session or not session.duration:
            continue
        capped = UserExerciseSession.capped_duration(
            session.duration, session.start_time, last_answer
        )
        if session.duration - capped >= MIN_CORRECTION_MS:
            result.append((session, capped))
    return sorted(result, key=lambda pair: pair[0].start_time)


def main(apply):
    found = runaway_sessions()
    print(f"{len(found)} exercise sessions counted long after their last answer:")
    for session, capped in found:
        user = session.user
        print(
            f"  session {session.id}: {user.name} <{user.email}> (user {user.id}), "
            f"{session.start_time:%Y-%m-%d %H:%M}, "
            f"{session.duration / 60000:.1f} min -> {capped / 60000:.1f} min"
        )
    if not apply:
        print("\nDry run. Run with --apply to store the lower times.")
        return
    for session, capped in found:
        session.duration = capped
    db.session.commit()
    print(f"\nStored the lower time for {len(found)} sessions.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)

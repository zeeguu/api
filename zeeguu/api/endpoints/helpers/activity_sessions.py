"""
    Function that captures a pattern that differs only in the name of the class
    between UserExerciseSession and UserReadingSession
"""

from datetime import datetime


def update_activity_session(session_class, request, db_session):
    form = request.form
    print(form)
    session_id = int(form.get("id", ""))
    duration = int(form.get("duration", 0))

    session = session_class.find_by_id(session_id)
    session.duration = duration
    session.last_action_time = datetime.now()
    db_session.add(session)
    db_session.commit()

    return session

from markupsafe import escape

from zeeguu.core.model import User
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
import human_readable
import datetime

cheers_your_server = "\n\rCheers,\n\rYour Zeeguu Server ;)"


def send_new_user_account_email(username, invite_code="", cohort=""):
    ZeeguuMailer.send_mail(
        f"New Account: {username}",
        [f"Code: {escape(invite_code)} Class: {escape(cohort)}", cheers_your_server],
    )


def send_user_finished_exercise_session(exercise_session):
    from zeeguu.core.sql.learner.exercises_history import exercises_in_session

    details = exercise_session.exercises_in_session_string()
    user = exercise_session.user

    # Calculate duration in a short format (e.g., "2min")
    duration_seconds = exercise_session.duration / 1000
    if duration_seconds < 60:
        duration_str = f"{int(duration_seconds)}sec"
    else:
        duration_minutes = int(duration_seconds / 60)
        duration_str = f"{duration_minutes}min"

    # Count unique words in the session
    exercises = exercises_in_session(exercise_session.id)
    unique_words = len(set(ex['user_word_id'] for ex in exercises))

    # Human readable duration for the body
    hr_duration = human_readable.precise_delta(
        datetime.timedelta(seconds=duration_seconds),
        minimum_unit="microseconds",
    )

    main_body = f"User: {escape(user.name)} ({user.id}, {escape(user.invitation_code)}) Duration: {hr_duration}  \n\n"
    main_body += f"<html><body><pre>{escape(details)}</pre></body></html>"

    # Format: "Julia: 2min, 14words"
    ZeeguuMailer.send_mail(
        f"{user.name}: {duration_str}, {unique_words}words",
        [main_body, cheers_your_server],
    )

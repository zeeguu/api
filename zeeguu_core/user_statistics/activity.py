from datetime import datetime, timedelta


def activity_by_day(user, time_interval=365):

    now = datetime.today()
    after_date = now - timedelta(days=time_interval)

    return user.reading_sessions_by_day(after_date, 100)

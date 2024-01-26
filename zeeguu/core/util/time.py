from datetime import datetime, timezone, timedelta


SERVER_HOUR_DIFFERENCE = 1  # Frankfurt is +1 from UTC


def get_server_time_utc():
    # Returns the time with the time delta of the server, converted
    # to UTC.
    return (
        datetime.now()
        .astimezone(timezone(timedelta(hours=SERVER_HOUR_DIFFERENCE)))
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


def normalize_to_server_time(date: datetime):
    return date.astimezone(timezone(timedelta(hours=SERVER_HOUR_DIFFERENCE))).replace(
        tzinfo=None
    )

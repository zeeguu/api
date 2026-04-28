from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


# ---------------------------------------------------------------------------
# Server-time constants
#
# These describe the timezone in which the API CONTAINER's libc clock runs
# — NOT the host's clock, NOT the project's "intended" timezone.
#
# Concretely: `datetime.now()` (and `time.time()`, MySQL `NOW()` from the
# DB container, etc.) returns whatever the libc inside that container
# thinks "local time" is. In `~/ops/running/api/docker-compose.yml` the
# `zapi` service does not pass `TZ=...` and does not bind-mount
# `/etc/localtime`, so libc defaults to UTC. The host (Hetzner box)
# reports `Europe/Berlin` from `date`, but Docker does NOT propagate the
# host's timezone into the container.
#
# As of 2026-04-29 the container is UTC, so SERVER_TZ = UTC and
# SERVER_HOUR_DIFFERENCE = 0.
#
# Why this matters: every naive datetime this codebase writes to the DB
# is a UTC clock reading. `to_user_local_date()` below stamps those
# naive values with SERVER_TZ before converting to the user's timezone,
# and `normalize_to_server_time()` writes new naive values at
# SERVER_HOUR_DIFFERENCE offset from UTC. If either constant disagrees
# with the container's libc, every user-facing date computation drifts
# by the gap — silently.
#
# History (issue #587): before the commit that introduced this comment,
# SERVER_TZ was `Europe/Berlin` while the container had been UTC the
# whole time. For users east of Berlin who practiced during the late
# UTC evening (their local post-midnight), `last_practiced` was misread
# as "still yesterday" on every session-update ping, so the streak
# incremented per-ping instead of once per day. Reproducer: a Bucharest
# user's Danish streak jumped 3 → 32 inside a single 6-minute audio
# lesson. The grayed "practiced today" indicator was the same bug.
#
# IMPORTANT — future ops changes:
# If anyone ever passes `TZ=Europe/Berlin` (or any other zone) to the
# `zapi` service, or bind-mounts `/etc/localtime` from the host, you
# MUST update both constants below in lockstep AND run a one-shot
# migration to translate every existing naive datetime column in the
# DB by the new offset. The mismatch is silent and re-corrupts streak
# math (and any other date arithmetic) the moment a container ships.
# Leave a release note. Tell the next person.
# ---------------------------------------------------------------------------
SERVER_HOUR_DIFFERENCE = 0  # Container's libc clock is UTC, so offset from UTC is 0.
SERVER_TZ = ZoneInfo("UTC")


def user_zone(user):
    if getattr(user, "timezone", None):
        try:
            return ZoneInfo(user.timezone)
        except ZoneInfoNotFoundError:
            pass
    return SERVER_TZ


def user_local_today(user):
    return datetime.now(user_zone(user)).date()


def to_user_local_date(user, naive_server_dt):
    if naive_server_dt is None:
        return None
    return naive_server_dt.replace(tzinfo=SERVER_TZ).astimezone(user_zone(user)).date()

"""
datetime (dt) is not by default a timezone aware object. When articles
are crawled we do get them as time aware objects. This is a problem
as timedeltas cannot be obtained by performing operations between 
a dt timezone aware object and a none dt timezone aware object.

There are 2 options, either all the time we have a datetime.now() we transform
it into a timezone aware object (what get_server_time_utc) does, or we normalize
all article dates to be based on the server.

1. Option would involve altering all the calls to datetime.now() in the code base
to get_server_time_utc(), and then with a time aware object we can perform time
delta operations. However, we also have to ensure all parsed dates are timezone aware.

2. Option normalizes all parsed data to the timezone of the server. This means all dates
that are stored in the DB have the same timezone (Frankfurt). It also means that all 
datetime objects are NOT timezone aware, which means all operations with datetime.now()
should not result in an exception. These objects can then be converted to any timezone
using the .astimezone() method.

We opt to go with the 2. option as using datetime.now() throughout the code for comparisons
means we have likely used the server time as reference for all our operations. This means
when an article gets parsed, we should call normalize_to_server_time(). 
"""


def get_server_time_utc():
    # Returns the time with the time delta of the server, converted
    # to UTC. This is now a time aware object. This can be useful
    # if we need to perform operations between the server time and
    # a timezone aware datetime object.
    # This is not used at this time, see explanation above.
    return (
        datetime.now()
        .astimezone(timezone(timedelta(hours=SERVER_HOUR_DIFFERENCE)))
        .astimezone(timezone.utc)
    )


def normalize_to_server_time(date: datetime):
    """
    Takes a datetime that MIGHT be a timezone aware object and converts it to
    the server time and makes it not time aware (so it can be operated on with datetime.now()).

    Examples:
    ## Case there is a non-tz aware object
    # A non-timezone aware object is created
    >>> example1 = datetime.fromisoformat('2011-11-04 10:05:23.283')
    datetime.datetime(2011, 11, 4, 10, 5, 23, 283000)
    >>> example1 - datetime.now()
    datetime.timedelta(days=-4473, seconds=1087, microseconds=670042)
    >>> example1_timeaware = example1.astimezone(timezone(timedelta(hours=1)))
    datetime.datetime(2011, 11, 4, 10, 5, 23, 283000, tzinfo=datetime.timezone(datetime.timedelta(seconds=3600)))
    >>> example1_timeaware - datetime.now()
    Traceback (most recent call last):
    File "<stdin>", line 1, in <module>
    TypeError: can't subtract offset-naive and offset-aware datetimes
    >>> example1_timeaware.replace(tzinfo=None)
    datetime.datetime(2011, 11, 4, 10, 5, 23, 283000)
    # We obtain the same object, it is assumed that the datetime was already in the server time.

    ## Case if there is a tz aware object
    # This time is +3 UTC, +2 from Frankfurt
    >>> example2 = datetime.fromisoformat('2011-11-04 10:05:23.283+03:00')
    datetime.datetime(2011, 11, 4, 10, 5, 23, 283000, tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))
    >>> example2_server_time = example2.astimezone(timezone(timedelta(hours=1)))
    datetime.datetime(2011, 11, 4, 8, 5, 23, 283000, tzinfo=datetime.timezone(datetime.timedelta(seconds=3600)))
    # Notice that the hours went back 2 in time (matches the fact that there is a 2 hour difference)
    >>> example2_server_time.replace(tzinfo=None)
    datetime.datetime(2011, 11, 4, 8, 5, 23, 283000)
    # We end up with a datetime object with the date converted to server time, not tz aware.

    """
    return date.astimezone(timezone(timedelta(hours=SERVER_HOUR_DIFFERENCE))).replace(
        tzinfo=None
    )


def human_readable_duration(duration_ms):
    """
    Convert a duration in milliseconds to a human readable string format in minutes.

    Args:
        duration_ms: Duration in milliseconds

    Returns:
        String in format "X.Xmin" (e.g., "4.5min")
    """
    return str(round(duration_ms / 1000 / 60, 1)) + "min"


def human_readable_date(date_time):
    """
    Convert a datetime object to a human readable date string.

    Args:
        date_time: A datetime object

    Returns:
        String representation of the date portion of the datetime
    """
    return str(datetime.date(date_time))

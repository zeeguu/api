from datetime import datetime, timezone, timedelta


SERVER_HOUR_DIFFERENCE = 1  # Frankfurt is +1 from UTC

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

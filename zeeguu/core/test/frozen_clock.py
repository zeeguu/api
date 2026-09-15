"""
Freeze the clock that every date computation in zeeguu.core.util.time reads.

Streak code answers questions like "did they practice *today*?", and the answer
depends on which timezone "today" is asked in. Tests that build their fixtures
from the wall clock of the machine running them only exercise whatever
UTC-vs-local relationship happens to hold at that moment -- which is why a suite
can be green all afternoon and fail after local midnight. Freezing the clock
lets a test name the instant it is testing, so both sides of a midnight are
covered on every run.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch


@contextmanager
def clock_at(utc_moment: str):
    """
    Pretend "now" is `utc_moment`, given as "YYYY-MM-DD HH:MM" in UTC.

    Patches the one function the module derives server_now() and
    user_local_today() from, so both move together.
    """
    frozen = datetime.fromisoformat(utc_moment).replace(tzinfo=timezone.utc)
    with patch("zeeguu.core.util.time._now_utc", return_value=frozen):
        yield frozen


def server_time_at(utc_moment: str) -> datetime:
    """The naive SERVER_TZ value the DB would hold for `utc_moment` (UTC)."""
    from zeeguu.core.util.time import SERVER_TZ

    return (
        datetime.fromisoformat(utc_moment)
        .replace(tzinfo=timezone.utc)
        .astimezone(SERVER_TZ)
        .replace(tzinfo=None)
    )

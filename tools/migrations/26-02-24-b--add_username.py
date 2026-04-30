#!/usr/bin/env python
"""
Migration script to back-fill usernames for existing users.

Why two strategies (active vs. inactive)?
-----------------------------------------
We have ~200 MAU out of several thousand total accounts. The small "pretty"
username pool — ADJECTIVES x ANIMALS = 20 x 18 = 360 no-digit combos — is a
scarce, renewable resource we'd rather spend on users who will actually see
their username in the UI (leaderboards, friend lists, profile). If we let the
migration greedily assign `adjective_animal` pairs to everyone in row order,
the pool evaporates before the active users even log in, and future signups
immediately spill into 4-digit suffixes.

So we partition by `last_seen`:

    * Active in the last 60 days -> prefer_no_digit=True  (tiered: no-digit
      first, then 1-digit, 2-digit, ... — see User.generate_unique_username)
    * Everyone else              -> prefer_no_digit=False (skip straight to
      4-digit; they can rename themselves later if they return)

Processing order matters: we handle the active partition first so it claims
the scarce no-digit pool before the inactive partition runs. The inactive
partition can't consume it anyway (prefer_no_digit=False jumps to tier 4),
but running active-first also makes the logs read in the expected order.

Running this script
-------------------
Must be run AFTER 26-02-24-a--add_username.sql (nullable column added).
Then 26-02-24-c--add_username.sql enforces NOT NULL + UNIQUE.

    pip install -e .
    set -a; source .env; set +a
    python tools/migrations/26-02-24-b--add_username.py
"""
from datetime import datetime, timedelta
from zeeguu.core.model.user_avatar import UserAvatar
from zeeguu.core.model.user import User


ACTIVE_WINDOW_DAYS = 60


def _now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]


def _assign(users: list[User], *, prefer_no_digit: bool, assigned_in_session: set[str], label: str):
    """Assign usernames + avatars for a partition of users. Returns avatar count."""
    total = len(users)
    avatar_count = 0
    for i, user in enumerate(users, 1):
        generated_username, _, animal = User.generate_unique_username(
            exclude=assigned_in_session,
            prefer_no_digit=prefer_no_digit,
        )
        assigned_in_session.add(generated_username)
        user.username = generated_username
        avatar_created = False
        animal_color = background_color = None
        # Create a matching avatar only if the user doesn't already have one.
        if UserAvatar.find(user.id) is None:
            animal_color, background_color = UserAvatar.random_colors()
            db.session.add(UserAvatar(user.id, animal, animal_color, background_color))
            avatar_created = True
            avatar_count += 1
        avatar_info = (
            f"created({animal_color}/{background_color})" if avatar_created else "exists"
        )
        print(
            f"{_now_str()} [{label} {i}/{total}] user_id={user.id} "
            f"-> username='{generated_username}' (avatar={avatar_info})"
        )
    return avatar_count


def populate_usernames():
    # Pull only users that actually need a username. We keep this as two
    # separate queries (rather than one + Python partition) so the active-vs-
    # inactive split is visible in the log line and so an interrupted run
    # restarts cleanly at the partition we were in.
    cutoff = datetime.now() - timedelta(days=ACTIVE_WINDOW_DAYS)

    active_users: list[User] = (
        User.query
        .filter(User.username.is_(None))
        .filter(User.last_seen.isnot(None))
        .filter(User.last_seen >= cutoff)
        .order_by(User.last_seen.desc())  # most recent first — nice names go to most engaged
        .all()
    )
    inactive_users: list[User] = (
        User.query
        .filter(User.username.is_(None))
        .filter((User.last_seen.is_(None)) | (User.last_seen < cutoff))
        .all()
    )

    total = len(active_users) + len(inactive_users)
    print(
        f"{_now_str()} Found {total} users without usernames "
        f"({len(active_users)} active in last {ACTIVE_WINDOW_DAYS}d, "
        f"{len(inactive_users)} inactive). Populating now..."
    )

    # Track usernames assigned in this run but not yet committed, so we don't
    # hand the same username to two users while the UNIQUE constraint is not
    # yet in place (it lands in step c).
    assigned_in_session: set[str] = set()

    avatar_count = _assign(
        active_users,
        prefer_no_digit=True,
        assigned_in_session=assigned_in_session,
        label="active",
    )
    avatar_count += _assign(
        inactive_users,
        prefer_no_digit=False,
        assigned_in_session=assigned_in_session,
        label="inactive",
    )

    # One commit at the end is 2-3x faster than committing per user.
    db.session.commit()
    print(
        f"{_now_str()} Done. Assigned {total} usernames "
        f"({len(active_users)} pretty / {len(inactive_users)} 4-digit), "
        f"created {avatar_count} avatars."
    )


if __name__ == "__main__":
    from zeeguu.api.app import create_app
    from zeeguu.core.model import db

    app = create_app()
    app.app_context().push()
    start_time = _now_str()
    print(f"{start_time} {'='*60}")
    print(f"{start_time} STARTING - username population...")
    try:
        populate_usernames()
    except Exception as e:
        print(f"{_now_str()} ERROR during username population: {e}")
    end_time = _now_str()
    total_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S.%f') - datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S.%f')
    print(f"{end_time} COMPLETED - username population. Total time: {total_time.seconds}s {total_time.microseconds // 1000}ms.")
    print(f"{end_time} {'='*60}")

from sqlalchemy.exc import IntegrityError


def find_or_create(session, cls, filters: dict, make, commit=False):
    """
    The row of `cls` matching `filters` (as for filter_by; relationship
    objects work too), created with `make()` if there is none.

    Safe when two requests create the same row at once, as long as a unique
    key covers `filters`: the loser gets the winner's row back.

    Commits only when it created the row and `commit` is set; a found or
    recovered row is returned without committing, as the per-model copies did.
    """
    row, _ = find_or_create_and_report(session, cls, filters, make, commit)
    return row


def find_or_create_and_report(session, cls, filters: dict, make, commit=False):
    """
    As find_or_create, but returns `(row, created)`: `created` is True only
    when this call inserted the row, and False when it found it or lost the
    race to another request. For callers that must do follow-up work (e.g.
    child rows) only for a row they created.
    """
    existing = session.query(cls).filter_by(**filters).one_or_none()
    if existing:
        return existing, False

    # Two requests that both miss the query above both insert, and the unique
    # key lets exactly one of them through.
    #
    # The savepoint is what makes losing survivable. A failed flush leaves the
    # whole session needing a rollback, so recovering without one raises
    # PendingRollbackError, and recovering with a full rollback throws away
    # whatever the caller had pending. Rolling back to a savepoint undoes this
    # insert and nothing else. `make()` runs inside the savepoint, so the new
    # object can't be flushed by begin_nested()'s own flush, outside it.
    try:
        with session.begin_nested():
            new = make()
            session.add(new)
    except IntegrityError:
        # A locking read (SELECT ... LOCK IN SHARE MODE). Under REPEATABLE
        # READ a plain SELECT would reuse this transaction's snapshot, taken
        # at its first read, before the winner committed: it would find
        # nothing and .one() would raise NoResultFound. A locking read sees
        # the latest committed row. (SQLite ignores it; tests don't race.)
        return (
            session.query(cls)
            .filter_by(**filters)
            .with_for_update(read=True)
            .one()
        ), False

    if commit:
        session.commit()
    return new, True

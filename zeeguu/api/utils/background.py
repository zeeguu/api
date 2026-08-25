import threading

from flask import current_app

from zeeguu.logging import log


def run_in_background(fn, *args, **kwargs):
    """
    Run a function in a background thread with a Flask app context.

    The function receives its own app context and db session,
    so it must re-query any SQLAlchemy objects by ID.

    Under `app.testing` the function runs inline instead (see below).

    Usage:
        run_in_background(my_function, arg1, arg2, kwarg1=val)
    """
    app = current_app._get_current_object()

    if app.testing:
        # Tests run against sqlite:///:memory:, which flask-sqlalchemy backs with a
        # StaticPool and check_same_thread=False -- so a "background" thread would
        # share the one and only connection with the test's own session and race it.
        # (Symptom: ObjectDeletedError on rows another session is midway through
        # writing, landing in whichever test happened to be running when the thread
        # woke up.) Inline keeps the job covered by the tests, and deterministic.
        try:
            fn(*args, **kwargs)
        except Exception as e:
            log(f"[background] Error in {fn.__name__}: {e}")
        return None

    def wrapper():
        with app.app_context():
            try:
                fn(*args, **kwargs)
            except Exception as e:
                log(f"[background] Error in {fn.__name__}: {e}")

    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    return thread

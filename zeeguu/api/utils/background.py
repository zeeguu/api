import threading

from flask import current_app

from zeeguu.logging import log


def run_in_background(fn, *args, **kwargs):
    """
    Run a function in a background thread with a Flask app context.

    The function receives its own app context and db session,
    so it must re-query any SQLAlchemy objects by ID.

    Usage:
        run_in_background(my_function, arg1, arg2, kwarg1=val)
    """
    app = current_app._get_current_object()

    def wrapper():
        with app.app_context():
            try:
                fn(*args, **kwargs)
            except Exception as e:
                log(f"[background] Error in {fn.__name__}: {e}")

    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    return thread

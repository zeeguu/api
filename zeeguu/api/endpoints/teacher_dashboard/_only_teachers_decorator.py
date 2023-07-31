import functools
import flask

from ._permissions import is_teacher


def only_teachers(view):
    """
    Decorator checks that user is a teacher
    """

    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        if not is_teacher(flask.g.user.id):
            flask.abort(401)
        return view(*args, **kwargs)

    return wrapped_view

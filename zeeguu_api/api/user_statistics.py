import flask

from . import api
from .utils.route_wrappers import cross_domain, with_session


@api.route("/bookmark_counts_by_date", methods=("GET",))
@cross_domain
@with_session
def bookmark_counts_by_date():
    """
    Words that have been learned with the help of the exercises
    """
    return flask.g.user.bookmark_counts_by_date()

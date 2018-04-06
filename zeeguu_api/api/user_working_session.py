import zeeguu
from zeeguu.model import UserWorkingSession

from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
import flask
from . import api


# ---------------------------------------------------------------------------
@api.route("/working_sessions_by_user", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def working_sessions_by_user():
    """
        Returns user_working_sessions data based on the provided filters for the specified user

        Parameters:
            user_id
            from_date   (using ISO-8601 format)
            to_date     (using ISO-8601 format)
            is_active

        Example: post
        http://localhost:9001/working_sessions_by_user?user_id=534&from_date=2017-02-24T00:00:00&to_date=2018-02-24T09:13:13&is_active=False&session=92752705
       
        return:
        [[session1], [session2], ... [sessionn]]
        where session
        [session_id, start_time, article_id, duration (in miliseconds)]
        Example:
        [
            [
                147,
                "2018-02-24T09:11:11",
                null,
                61
            ],
            ...
        ]
    """
    user_id =  int(flask.request.args['user_id'])
    from_date = flask.request.args['from_date']
    to_date = flask.request.args['to_date']
    is_active = bool(flask.request.args['is_active'])
    active_sessions = UserWorkingSession.find_by_user(user_id, from_date, to_date, is_active)
    result = [[item.id, item.start_time.isoformat(), item.article_id, item.duration] for item in active_sessions]
    return json_result(result)


# ---------------------------------------------------------------------------
@api.route("/working_sessions_by_cohort", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def working_sessions_by_cohort():
    """
        Returns user_working_session data based on the provided filters for the specified cohort

        Parameters:
            cohort_id
            from_date   (using ISO-8601 format)
            to_date     (using ISO-8601 format)
            is_active

        Example: post
        http://localhost:9001/working_sessions_by_cohort?cohort_id=1&from_date=2010-01-24T00:00:00&to_date=2018-02-24T09:13:13&is_active=False&session=92752705
        
        return:
        [[session1], [session2], ... [sessionn]]
        where sessionn
        [user_working_session.id, user_id, start_time, article_id, duration (in miliseconds)]
        Example:
        [
            [
                48,
                617,
                "2017-05-19T14:58:58",
                63399,
                0
            ],
            ...
        ]
    """
    cohort_id =  int(flask.request.args['cohort_id'])
    from_date = flask.request.args['from_date']
    to_date = flask.request.args['to_date']
    is_active = bool(flask.request.args['is_active'])
    active_sessions = UserWorkingSession.find_by_cohort(cohort_id, from_date, to_date, is_active)
    result = [[item.id, item.user_id, item.start_time.isoformat(), item.article_id, item.duration] for item in active_sessions]
    return json_result(result)


# ---------------------------------------------------------------------------
@api.route("/working_sessions_by_cohort_and_article", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def working_sessions_by_cohort_and_article():
    """
        Returns user_working_session data based on the provided filters for the specified article and cohort

        Parameters:
            cohort_id
            article_id
            from_date   (using ISO-8601 format)
            to_date     (using ISO-8601 format)
            is_active

        Example: post
        http://localhost:9001/working_sessions_by_cohort_and_article?cohort_id=1&article_id=63400&from_date=2010-01-24T00:00:00&to_date=2018-02-25T09:13:13&is_active=False&session=92752705

        return:
        [[session1], [session2], ..., [sessionn]]
        where sessionn
        [user_working_session.id, user_id, start_time, duration (in miliseconds)]
        Example:
        [
            [
                51,
                617,
                "2017-05-19T14:59:59",
                0
            ],
            ...
        ]
    """
    cohort_id =  int(flask.request.args['cohort_id'])
    article_id =  int(flask.request.args['article_id'])
    from_date = flask.request.args['from_date']
    to_date = flask.request.args['to_date']
    is_active = bool(flask.request.args['is_active'])
    active_sessions = UserWorkingSession.find_by_article(article_id, from_date, to_date, is_active, cohort_id)
    result = [[item.id, item.user_id, item.start_time.isoformat(), item.duration] for item in active_sessions]
    return json_result(result)


# ---------------------------------------------------------------------------
@api.route("/working_sessions_by_user_and_article", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def working_sessions_by_user_and_article():
    """
        Returns user_working_session data based on the provided filters for the specified article and user

        Parameters:
            user_id
            article_id

        Example: post
        http://localhost:9001/working_sessions_by_user_and_article?user_id=617&article_id=63400&session=92752705

        return:
        [[session1], [session2], ..., [sessionn]]
        where sessionn
        [user_working_session.id, start_time, duration (in miliseconds)]
        Example:
        [
            [
                51,
                "2017-05-19T14:59:59",
                0
            ],
            ...
        ]
    """
    user_id =  int(flask.request.args['user_id'])
    article_id =  int(flask.request.args['article_id'])
    active_sessions = UserWorkingSession.find_by_user_and_article(user_id, article_id)
    result = [[item.id, item.start_time.isoformat(), item.duration] for item in active_sessions]
    return json_result(result)
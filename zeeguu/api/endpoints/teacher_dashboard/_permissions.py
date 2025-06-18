import flask
import sqlalchemy
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.core.model.teacher import Teacher
from zeeguu.core.model.user import User


def has_permission_for_cohort(cohort_id):
    """
    Checks to see if user requesting has permissions
    to view the cohort with id 'cohort_id'
    """
    from zeeguu.core.model.teacher_cohort_map import TeacherCohortMap

    maps = TeacherCohortMap.query.filter_by(cohort_id=cohort_id).all()
    for m in maps:
        if m.user_id == flask.g.user_id:
            return True
    return False


def check_permission_for_cohort(cohort_id):
    if not has_permission_for_cohort(cohort_id):
        flask.abort(401)


def check_permission_for_user(user_id, cohort_id):
    try:
        user = User.query.filter_by(id=user_id).one()
        if user.is_member_of_cohort(cohort_id):
            return user
        flask.abort(401)
    except KeyError:
        flask.abort(400)
        return "KeyError"
    except sqlalchemy.orm.exc.NoResultFound:
        flask.abort(400)
        return "NoResultFound"


def is_teacher(user_id):
    try:
        Teacher.query.filter_by(user_id=user_id).one()
        return True
    except NoResultFound:

        return False

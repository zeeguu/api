import flask
import sqlalchemy


from zeeguu.core.model import Cohort, User, Language
from zeeguu.core.sql.teacher.teachers_for_cohort import teachers_for_cohort
from zeeguu.core.user_statistics.exercise_corectness import (
    exercise_count_and_correctness_percentage,
)
from zeeguu.core.user_statistics.exercise_sessions import (
    total_time_in_exercise_sessions,
)
from zeeguu.core.user_statistics.reading_sessions import summarize_reading_activity


def student_info_for_teacher_dashboard(user, cohort, from_date: str, to_date: str):

    info = {"id": user.id, "name": user.name, "email": user.email}

    info.update(summarize_reading_activity(user.id, cohort.id, from_date, to_date))
    info.update(total_time_in_exercise_sessions(user.id, cohort.id, from_date, to_date))
    info.update(
        exercise_count_and_correctness_percentage(
            user.id, cohort.id, from_date, to_date
        )
    )

    return info


def all_user_info_from_cohort(id, from_date: str, to_date: str):
    """
    Takes id for a cohort and returns all users belonging to that cohort.
    """
    c = Cohort.query.filter_by(id=id).one()
    users = User.query.filter_by(cohort_id=c.id).all()
    users_info = []

    for u in users:
        info = student_info_for_teacher_dashboard(u, c, from_date, to_date)

        users_info.append(info)
    return users_info


def get_cohort_info(id):
    """
    Takes id of cohort and returns dictionary with id, name, inv_code, max_students, cur_students and language_name
    """
    try:
        c = Cohort.find(id)
        name = c.name
        inv_code = c.inv_code
        max_students = c.max_students
        cur_students = c.get_current_student_count()

        try:
            language_id = c.language_id
            language = Language.query.filter_by(id=language_id).one()
            language_name = language.name

        except ValueError:
            language_name = "None"
        except sqlalchemy.orm.exc.NoResultFound:
            language_name = "None"
        dictionary = {
            "id": str(id),
            "name": name,
            "inv_code": inv_code,
            "max_students": max_students,
            "cur_students": cur_students,
            "language_name": language_name,
            "declared_level_min": c.declared_level_min,
            "declared_level_max": c.declared_level_max,
            "teachers_for_cohort": teachers_for_cohort(id),
        }
        return dictionary
    except ValueError:
        flask.abort(400)
        return "ValueError"
    except sqlalchemy.orm.exc.NoResultFound:
        flask.abort(400)
        return "NoResultFound"

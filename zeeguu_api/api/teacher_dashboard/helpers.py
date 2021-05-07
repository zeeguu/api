import flask
import sqlalchemy

from zeeguu_core.model.student import Student

from zeeguu_core.model import Cohort, User, Language


def all_user_info_from_cohort(id, duration):
    """
    Takes id for a cohort and returns all users belonging to that cohort.
    """
    c = Cohort.query.filter_by(id=id).one()
    users = User.query.filter_by(cohort_id=c.id).all()
    users_info = []
    for u in users:
        info = student_info_for_teacher_dashboard(u.id, duration)
        users_info.append(info)
    return users_info


def student_info_for_teacher_dashboard(id, duration):
    """
    Takes id for a cohort and returns a dictionary with
    id,name,email,reading_time,exercises_done and last article

    """

    student = Student(id)
    return student.info_for_teacher_dashboard(duration)


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
        }
        return dictionary
    except ValueError:
        flask.abort(400)
        return "ValueError"
    except sqlalchemy.orm.exc.NoResultFound:
        flask.abort(400)
        return "NoResultFound"

"""Finding things in the classroom.

Everything here is implementation: it walks the model, applies the rules from
classroom/rules.py, and hands back the answer. No policy is decided in this
file -- a condition about what a student may see belongs next door.
"""

from zeeguu.core.classroom.rules import app_is_reduced_to_classroom, student_can_read


def classes_of(user):
    """The classes a user is enrolled in.

    Enrolment, not ownership: a teacher who owns a class is not in it unless
    they joined it like a student.
    """
    from zeeguu.core.model.cohort import Cohort

    return [Cohort.find(membership.cohort_id) for membership in user.cohorts]


def texts_of(cohort):
    """Every text a teacher has shared with this class, in any language."""
    from zeeguu.core.model.cohort_article_map import CohortArticleMap

    return CohortArticleMap.get_articles_for_cohort(cohort)


def classroom_of(student):
    """The texts a student sees, each with the classes it reached them through.

    One merged list: a student in several classes has one classroom, not one
    per class, and a text shared with two of them appears once naming both.

    Returns [(Article, [Cohort])], in the order the classes were joined.
    """
    reached_through = {}
    order = []

    for cohort in classes_of(student):
        for text in texts_of(cohort):
            if not student_can_read(student, text):
                continue
            if text.id not in reached_through:
                order.append(text)
                reached_through[text.id] = []
            reached_through[text.id].append(cohort)

    return [(text, reached_through[text.id]) for text in order]


def hidden_from(student):
    """The texts in the student's classes that they cannot open.

    The reason a class can look full to its teacher and empty to half of its
    students.
    """
    return [
        text
        for cohort in classes_of(student)
        for text in texts_of(cohort)
        if not student_can_read(student, text)
    ]


def sees_only_class_texts(user):
    """Whether the app is reduced to the classroom for this user."""
    return app_is_reduced_to_classroom(user, classes_of(user))

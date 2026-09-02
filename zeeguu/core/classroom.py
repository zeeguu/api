"""Who sees which class texts.

The whole of the classroom, in the order someone would ask about it:

    which classes is this student in?
    which texts are in those classes?
    which of those can the student actually read?
    and is the classroom the whole app for them?

Each rule below is one function and the sentence that justifies it. Everything
that is not a rule -- queries, caching, serialising to JSON -- lives elsewhere
and calls in here. The rules used to be spread across User, the feature
toggles and the article filters, which is why they kept being got wrong.

test_classroom_visibility_rules.py states the same rules as a table of worlds
and expected outcomes; it is the check that this file still means what it says.
"""


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


def student_can_read(student, text):
    """A student reads only in the language they are currently learning.

    The student's own setting decides, not the class's -- which is why a
    Greek learner in an English class sees an empty classroom, and why a class
    can hold texts that nobody in it can open.
    """
    if student.learned_language is None:
        return False
    return text.language_id == student.learned_language_id


def classroom_of(student):
    """The texts a student sees, each with the classes it reached them through.

    One merged list: a student in several classes has one classroom, not one
    per class. A text shared with two of their classes appears once, naming
    both.

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

    The other half of student_can_read, and the reason a class can look full
    to its teacher and empty to half its students.
    """
    return [
        text
        for cohort in classes_of(student)
        for text in texts_of(cohort)
        if not student_can_read(student, text)
    ]


def sees_only_class_texts(user):
    """Whether the app is reduced to the classroom: no feed, no search, no inbox.

    A teacher sets it per class. A student in several classes is restricted if
    any one of them asks for it -- the strictest class wins, and the way out is
    to leave that class.

    Teachers are never restricted, even in a class that asks for it: they need
    the feed and the search to find the texts they are going to share. This is
    why a teacher clicking "Student Site" is shown the full app and cannot see
    what their own students see.
    """
    if user.isTeacher():
        return False

    return any(cohort.only_classroom_texts for cohort in classes_of(user))

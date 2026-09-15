"""The classroom's rules. Nothing else lives here.

Each function below is a policy: it answers "is this allowed?" from values it
is given, and touches no database. That is the point of the file -- you can
read it end to end in under a minute, and there is nowhere for behaviour to
hide, because there is no traversal, no query and no I/O.

Anything that has to *find* things -- which classes a student is in, which
texts are in them -- is a query and lives in classroom/queries.py. Those call
these; these never call those.

test_classroom_visibility_rules.py states the same rules as a table of worlds
and expected outcomes.
"""


def student_can_read(student, text):
    """A student reads only in the language they are currently learning.

    The student's own setting decides, not the class's -- which is why a Greek
    learner in an English class sees an empty classroom, and why a class can
    hold texts that nobody in it can open.
    """
    if student.learned_language is None:
        return False
    return text.language_id == student.learned_language_id


def app_is_reduced_to_classroom(user, classes):
    """Whether this user gets only the classroom: no feed, no search, no inbox.

    A teacher sets it per class. A student in several classes is restricted if
    any one of them asks for it -- the strictest class wins, and the way out is
    to leave that class.

    Teachers are never restricted, even in a class that asks for it: they need
    the feed and the search to find the texts they are going to share. This is
    why a teacher clicking "Student Site" gets the full app, and cannot see
    what their own students see.
    """
    if user.isTeacher():
        return False

    return any(cohort.only_classroom_texts for cohort in classes)

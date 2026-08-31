"""What a student may see in their classroom, as a table.

Every row is one world, and what a student in it sees. These rules are spread
across cohort_articles_for_user, _classroom_only and the article filters; no
one file states them, which is why they keep being got wrong. State them here
and let the real code answer.

Read a row as:

    a student LEARNING this language, enrolled in these CLASSES,
    sees SEES texts, and their app is in MODE.

In CLASSES, the value is the language of each text in that class, so
"en en da" is a class holding two English texts and one Danish. A class name
ending in ! has "students see only the texts I share" switched on.
"""

from unittest import TestCase

import zeeguu.core
from zeeguu.core.model.cohort import Cohort
from zeeguu.core.model.cohort_article_map import CohortArticleMap
from zeeguu.core.model.teacher import Teacher
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.user_feature_toggles import is_feature_enabled_for_user

db_session = zeeguu.core.model.db.session

FULL_APP = "full app"
CLASSROOM_ONLY = "classroom only"

#        learning  classes                                sees  mode
RULES = [
    ("the ordinary case",
         "da",     {"Danish Class": "da da da"},            3,   FULL_APP),

    ("a class in another language is invisible, not empty",
         "da",     {"English Class": "en en"},              0,   FULL_APP),

    ("a class may hold texts the student cannot see",
         "da",     {"Mixed Class": "da en en"},             1,   FULL_APP),

    ("two classes merge into one list",
         "da",     {"A": "da", "B": "da"},                  2,   FULL_APP),

    ("a text in two of the student's classes is listed once",
         "da",     {"A": "shared", "B": "shared"},          1,   FULL_APP),

    ("one restricted class restricts the whole app",
         "da",     {"A": "da da", "B!": "da"},              3,   CLASSROOM_ONLY),

    ("Jack's bug: restricted, and every text is in another language",
         "de",     {"CUT!": "en en en en en"},              0,   CLASSROOM_ONLY),

    ("a student with no language set sees nothing",
         None,     {"Danish Class": "da da"},               0,   FULL_APP),
]


class ClassroomVisibilityRulesTest(ModelTestMixIn, TestCase):
    def _language(self, code):
        return LanguageRule.get_or_create_language(code)

    _next_code = 0

    def _world(self, learning, classes):
        student = UserRule().user
        if learning:
            student.set_learned_language(learning, session=db_session)
        else:
            student.learned_language = None

        shared_article = None
        for name, text_languages in classes.items():
            # invite codes are unique across the whole table, and class names
            # repeat between rows
            ClassroomVisibilityRulesTest._next_code += 1
            cohort = Cohort(f"code-{ClassroomVisibilityRulesTest._next_code}",
                            name.rstrip("!"),
                            self._language("da"), 10,
                            only_classroom_texts=name.endswith("!"))
            db_session.add(cohort)
            student.add_user_to_cohort(cohort, db_session)

            for code in text_languages.split():
                if code == "shared":
                    # the same article, deliberately, in both classes
                    if shared_article is None:
                        shared_article = ArticleRule().article
                        shared_article.language = self._language("da")
                    article = shared_article
                else:
                    article = ArticleRule().article
                    article.language = self._language(code)
                db_session.add(article)
                db_session.add(CohortArticleMap(cohort, article, None))
        db_session.commit()
        return student

    def test_every_rule(self):
        for label, learning, classes, sees, mode in RULES:
            with self.subTest(label):
                student = self._world(learning, classes)

                self.assertEqual(
                    sees, len(student.cohort_articles_for_user()),
                    f"{label}: wrong number of texts visible")

                restricted = is_feature_enabled_for_user("classroom_only", student)
                self.assertEqual(
                    mode, CLASSROOM_ONLY if restricted else FULL_APP,
                    f"{label}: wrong mode")

    def test_a_teacher_is_never_restricted(self):
        # Stated separately because it is about who you are, not what you see.
        teacher = self._world("da", {"A!": "da"})
        db_session.add(Teacher(teacher))
        db_session.commit()

        self.assertFalse(is_feature_enabled_for_user("classroom_only", teacher))

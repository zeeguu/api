from datetime import datetime, timedelta
from random import randint
from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.cohort_rule import CohortRule
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.model.user_reading_session import UserReadingSession



class ReadingSessionRule(BaseRule):
    """

        Creates a Reading Session object with random data and saves it to the database.

    """
    def __init__(self):
        super().__init__()

        self.w_session = self._create_model_object()

        self.save(self.w_session)

    def _create_model_object(self):
        cohort = CohortRule()
        user = cohort.student1
        article = ArticleRule().article
        start_time = datetime.now() - timedelta(minutes=randint(0, 7200))

        w_session = UserReadingSession(user.id, article.id, start_time)

        return w_session

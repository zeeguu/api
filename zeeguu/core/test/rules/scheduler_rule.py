from zeeguu.core.test.rules.base_rule import BaseRule


class SchedulerRule(BaseRule):
    """A Rule testing class for the zeeguu.core.model.User model class.

    Creates a User object with random data and saves it to the database.
    """

    def __init__(self, scheduler_model, user_meaning, db_session):
        super().__init__()

        self.schedule = self._create_model_object(
            scheduler_model, user_meaning, db_session
        )
        self.save(self.schedule)

    def _create_model_object(self, scheduler_model, user_meaning, db_session):
        schedule = scheduler_model.find_or_create(db_session, user_meaning)
        return schedule

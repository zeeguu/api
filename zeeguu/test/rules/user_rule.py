from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.exercise_rule import ExerciseRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.model.user import User


class UserRule(BaseRule):
    """A Rule testing class for the zeeguu.core.model.User model class.

    Creates a User object with random data and saves it to the database.
    """

    def __init__(self):
        super().__init__()

        self.user = self._create_model_object()
        self.save(self.user)
        self.user.create_default_user_preference()

    def _create_model_object(self):
        random_email = self.faker.simple_profile()["mail"]
        random_name = self.faker.name()
        random_password = self.faker.password()
        random_learned_language = LanguageRule().random
        random_native_language = LanguageRule().random

        while random_native_language.id == random_learned_language.id:
            random_native_language = LanguageRule().random

        user = User(
            random_email,
            random_name,
            random_password,
            learned_language=random_learned_language,
            native_language=random_native_language,
        )

        if self._exists_in_db(user):
            return self._create_model_object()
        return user

    @staticmethod
    def _exists_in_db(obj):
        return User.exists(obj)

    def add_bookmarks(self, bookmark_count, exercises_count=0, **kwargs):
        bookmark_rules = []

        for _ in range(bookmark_count):
            bookmark_rule = BookmarkRule(self.user, **kwargs)
            bookmark = bookmark_rule.bookmark

            for i in range(0, exercises_count):
                random_exercise = ExerciseRule().exercise
                bookmark.add_new_exercise(random_exercise)

            bookmark_rules.append(bookmark_rule)
        return bookmark_rules

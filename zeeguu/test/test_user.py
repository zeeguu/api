import json
import random
import uuid
from collections import Counter
from datetime import datetime, timedelta

from dateutil.utils import today
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.model import User
from zeeguu.core.model import db


class UserTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user

    def test_create_anonymous(self):
        self.user = UserRule().user
        new_password = self.faker.password()
        self.user.update_password(new_password)

        user_to_check = User.create_anonymous(
            str(self.user.id),
            new_password,
            self.user.learned_language.code,
            self.user.native_language.code,
        )

        assert user_to_check.email == str(self.user.id) + User.ANONYMOUS_EMAIL_DOMAIN
        assert user_to_check.name == str(self.user.id)
        assert user_to_check.learned_language == self.user.learned_language
        assert user_to_check.native_language == self.user.native_language

    def test_date_of_last_bookmark(self):
        random_bookmarks = [
            BookmarkRule(self.user).bookmark for _ in range(random.randint(2, 5))
        ]
        random_bookmarks[-1].time = datetime.now()

        last_bookmark_time = self.user.date_of_last_bookmark()

        assert (
            last_bookmark_time == random_bookmarks[-1].time
        ), "{0} should be {1}".format(last_bookmark_time, random_bookmarks[-1].time)

    def test_active_during_recent(self):
        # User has no bookmarks, so he/she was not active recently
        assert not self.user.active_during_recent()

        random_bookmark = BookmarkRule(self.user).bookmark
        random_bookmark.time = datetime.now()
        assert self.user.active_during_recent()

    def test_validate_email(self):
        random_email = self.faker.email()
        assert User.validate_email("", random_email)

    def test_validate_password(self):
        random_password = self.faker.password()
        assert User.validate_password("", random_password)

    def test_validate_name(self):
        random_name = self.faker.name()
        assert User.validate_name("", random_name)

    def test_update_password(self):
        password_before = self.user.password
        password_after = self.user.update_password(self.faker.password())

        assert password_before != password_after

    def test_all_bookmarks(self):
        random_bookmarks = [
            BookmarkRule(self.user).bookmark for _ in range(random.randint(2, 5))
        ]
        bookmarks_retrieved = self.user.all_bookmarks()

        assert all([b in bookmarks_retrieved for b in random_bookmarks])

    def test_bookmarks_chronologically(self):
        random_bookmarks = [
            BookmarkRule(self.user).bookmark for _ in range(random.randint(2, 5))
        ]
        random_bookmarks_ordered = sorted(
            random_bookmarks, key=lambda b: b.time, reverse=True
        )

        assert self.user.bookmarks_chronologically() == random_bookmarks_ordered

    def test_bookmarks_by_date(self):
        random_bookmarks = [
            BookmarkRule(self.user).bookmark for _ in range(random.randint(2, 5))
        ]
        random_bookmarks_dates = [
            self.__truncate_time_from_date(b.time) for b in random_bookmarks
        ]
        random_bookmarks_dates_count = dict(Counter(random_bookmarks_dates))

        result_bookmarks, result_dates_sorted = self.user.bookmarks_by_date()

        for day, bookmarks in result_bookmarks.items():
            assert len(bookmarks) == random_bookmarks_dates_count[day]

    def test_bookmark_counts_by_date(self):
        date_bookmark_pair = []
        for i in range(random.randint(5, 10)):
            today_without_time = self.__truncate_time_from_date(today())
            random_date = today_without_time - timedelta(random.randint(1, 364))

            random_bookmark = BookmarkRule(self.user).bookmark
            random_bookmark.time = random_date

            date_bookmark_pair.append(random_date)

        date_bookmark_count_pair = dict(Counter(date_bookmark_pair))

        counts_by_date = json.loads(self.user.bookmark_counts_by_date())

        for pair in counts_by_date:
            result_date = datetime.strptime(pair["date"], "%Y-%m-%d")
            result_count = pair["count"]

            assert result_date in date_bookmark_count_pair
            assert result_count == date_bookmark_count_pair[result_date]

    def test_exists(self):
        assert User.exists(self.user)

    def test_authorize(self):
        new_password = self.faker.password()
        self.user.update_password(new_password)
        result = User.authorize(self.user.email, new_password)

        assert result is not None and result == self.user

    def test_authorize_anonymous(self):
        random_uuid = str(uuid.uuid4())
        new_password = self.faker.password()
        anonymous_user = User.create_anonymous(random_uuid, new_password)
        db.session.add(anonymous_user)
        db.session.commit()

        result = User.authorize_anonymous(random_uuid, new_password)

        assert result is not None and result == anonymous_user

    def __truncate_time_from_date(self, date_with_time):
        return datetime(
            date_with_time.year, date_with_time.month, date_with_time.day, 0, 0, 0
        )

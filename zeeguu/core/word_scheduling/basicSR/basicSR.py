from zeeguu.core.model import Bookmark, UserWord

import zeeguu.core
from zeeguu.core.model.bookmark import CORRECTS_IN_A_ROW_FOR_LEARNED
from zeeguu.core.sql.query_building import list_of_dicts_from_query

from zeeguu.core.model import db

from datetime import datetime, timedelta

ONE_DAY = 60 * 24

NEXT_COOLING_INTERVAL_ON_SUCCESS = {
    0: ONE_DAY,
    ONE_DAY: 2 * ONE_DAY,
    2 * ONE_DAY: 4 * ONE_DAY,
    4 * ONE_DAY: 8 * ONE_DAY,
}


class BasicSRSchedule(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "basic_sr_schedule"

    id = db.Column(db.Integer, primary_key=True)

    bookmark = db.relationship(Bookmark)
    bookmark_id = db.Column(db.Integer, db.ForeignKey(Bookmark.id), nullable=False)

    next_practice_time = db.Column(db.DateTime, nullable=False)
    consecutive_correct_answers = db.Column(db.Integer)
    cooling_interval = db.Column(db.Integer)

    def __init__(self, bookmark=None, bookmark_id=None):
        if bookmark_id:
            self.bookmark_id = bookmark_id
        else:
            self.bookmark = bookmark
        self.next_practice_time = datetime.now()
        self.consecutive_correct_answers = 0
        self.cooling_interval = 0

    def update_schedule(self, db_session, correctness):
        if correctness:

            if self.consecutive_correct_answers == CORRECTS_IN_A_ROW_FOR_LEARNED - 1:
                self.bookmark.learned = True
                self.bookmark.learned_time = datetime.now()
                db.session.add(self.bookmark)
                db.session.commit()
                db.session.delete(self)
                db.session.commit()
                return

            if datetime.now() < self.next_practice_time:
                # a user might have arrived here by doing the
                # bookmarks in a text for a second time...
                # in general, as long as they didn't wait for the
                # cooldown perio, they might have arrived to do
                # the exercise again; but it should not count
                return

            new_cooling_interval = NEXT_COOLING_INTERVAL_ON_SUCCESS[
                self.cooling_interval
            ]
            next_practice_date = datetime.now() + timedelta(
                minutes=new_cooling_interval
            )
            self.cooling_interval = new_cooling_interval
            self.next_practice_time = next_practice_date
            self.consecutive_correct_answers += 1

        else:
            self.next_practice_time = datetime.now()
            self.cooling_interval = 0
            self.consecutive_correct_answers = 0

        db_session.add(self)
        db_session.commit()

    @classmethod
    def update(cls, db_session, bookmark, correctness):
        schedule = cls.find_or_create(db_session, bookmark)
        schedule.update_schedule(db_session, correctness)

    @classmethod
    def find_or_create(cls, db_session, bookmark):

        results = cls.query.filter_by(bookmark=bookmark).all()
        print(results)
        if len(results) == 1:
            print(len(results))
            print("getting the first element in results")
            return results[0]

        if len(results) > 1:
            raise Exception(
                f"More than one Bookmark schedule entry found for {bookmark.id}"
            )

        # create a new one
        b = cls(bookmark)
        db_session.add(b)
        db_session.commit()
        return b

    @classmethod
    def bookmarks_to_study(cls, user, required_count):
        scheduled = (
            Bookmark.query.join(cls)
            .filter(Bookmark.user_id == user.id)
            .join(UserWord, Bookmark.origin_id == UserWord.id)
            .filter(UserWord.language_id == user.learned_language_id)
            .filter(cls.next_practice_time < datetime.now())
            .limit(required_count)
            .all()
        )

        return scheduled

    @classmethod
    def schedule_some_more_bookmarks(cls, session, user, required_count):

        from zeeguu.core.sql.queries.query_loader import load_query

        query = load_query("words_to_study")
        result = list_of_dicts_from_query(
            query,
            {
                "user_id": user.id,
                "language_id": user.learned_language.id,
                "required_count": required_count,
            },
        )

        for b in result:
            print(b)
            id = b["bookmark_id"]
            b = Bookmark.find(id)
            print(f"scheduling another bookmark_id for now: {id} ")
            n = cls(b)
            print(n)
            session.add(n)

        session.commit()

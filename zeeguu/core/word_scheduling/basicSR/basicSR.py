from zeeguu.core.model import Bookmark

import zeeguu.core

db = zeeguu.core.db

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

    def __init__(self, bookmark):
        self.bookmark = bookmark
        self.next_practice_time = datetime.now()
        self.consecutive_correct_answers = 0
        self.cooling_interval = 0

    def update(self, db_session, correctness):

        if correctness:
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
        schedule.update(db_session, correctness)

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
    def bookmarks_to_study(cls, user):
        return (
            Bookmark.query.join(cls)
            .filter(Bookmark.user_id == user.id)
            .filter(cls.next_practice_time < datetime.now())
            .all()
        )

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.exc import IntegrityError

from zeeguu.core.model.db import db


class EvergreenImpression(db.Model):
    """
    An article the Evergreen tab has shown a learner: when first, when last,
    and how often.

    The tab exists to show something new on every visit. It can only do that
    if it remembers what it already showed: an article shown on an earlier day
    and not opened drops behind the ones the learner has never seen.

    "Shown" means listed on the tab, not opened; opening is in user_article.
    """

    __tablename__ = "evergreen_impression"
    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_evergreen_impression_user_article"),
        {"mysql_collate": "utf8mb4_unicode_ci"},
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    article_id = Column(Integer, ForeignKey("article.id", ondelete="CASCADE"), nullable=False)
    first_shown = Column(DateTime, nullable=False)
    last_shown = Column(DateTime, nullable=False)
    times_shown = Column(Integer, nullable=False, default=1)

    def __init__(self, user_id, article_id, when):
        self.user_id = user_id
        self.article_id = article_id
        self.first_shown = when
        self.last_shown = when
        self.times_shown = 1

    @classmethod
    def for_user(cls, user_id):
        """{article_id: impression} for everything the tab ever showed this user."""
        return {i.article_id: i for i in cls.query.filter_by(user_id=user_id).all()}

    @classmethod
    def record(cls, session, user_id, article_ids, known=None, when=None):
        """Note that these articles were just listed. `known` is the dict
        for_user returned, so the caller's one read is reused. Showing the same
        list twice in a day counts once: times_shown counts days, which is what
        "seen it and passed it by" means."""
        when = when or datetime.now()
        known = known if known is not None else cls.for_user(user_id)
        for article_id in article_ids:
            impression = known.get(article_id)
            if impression is None:
                session.add(cls(user_id, article_id, when))
            elif impression.last_shown.date() != when.date():
                impression.last_shown = when
                impression.times_shown += 1
        try:
            session.commit()
        except IntegrityError:
            # Two loads of the tab at once both inserted the same article.
            # The other one recorded it: losing this write loses nothing.
            session.rollback()

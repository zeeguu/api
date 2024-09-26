import sqlalchemy
from zeeguu.api.utils.abort_handling import make_error
import zeeguu.core
from sqlalchemy import Column, Integer, String

from zeeguu.core.model import db


class FeedbackComponent(db.Model):
    """

    A Feedback Component is a component of the Web that the user
    can report an issue from. They pick one from a drop-down list
    based on the URL/component they are currently at.

    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)
    component_type = Column(String(45))

    def __init__(self, component_type):
        self.component_type = component_type

    def __repr__(self):
        return f"<FeedbackComponent: {self.component_type}>"

    def as_dictionary(self):

        return dict(
            id=self.id,
            component_type=self.component_type,
        )

    @classmethod
    def get_all_options(cls):
        return cls.query.all()

    @classmethod
    def find_or_create(cls, session, component_type):
        try:
            return cls.query.filter(cls.component_type == component_type).one()
        except sqlalchemy.orm.exc.NoResultFound:
            new = cls(component_type)
            session.add(new)
            return new

    @classmethod
    def find(cls, component_type):
        try:
            search = cls.query.filter(cls.component_type == component_type).one()
            return search
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find_by_id(cls, i):
        try:
            result = cls.query.filter(cls.id == i).one()
            return result
        except Exception as e:
            from sentry_sdk import capture_exception

            capture_exception(e)
            return None

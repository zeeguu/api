from faker import Faker
from sqlalchemy.exc import InvalidRequestError

import zeeguu.core.model


class BaseRule:
    """The base class for the Rule testing framework.
    Holds functions to save an object to the database.
    If the functionality of how to save an object to the database changes, it only needs to be changed here.

    Dedicated Rule classes, which actually create the random objects inherit from this rule class and need to
    implement the '_create_model_object' and '_exists_in_db' function.

    The Rule testing framework uses Rule classes in order to create random objects from the classes defined in the
    zeeguu/model package for testing purposes.

    This way, random model objects can be created and deleted after each unit test.

    The Faker library is used to create the random data.
    """

    faker = Faker()

    from zeeguu.core.model import db

    @classmethod
    def save(cls, obj):
        try:
            cls.db.session.add(obj)
            cls.db.session.commit()
        except InvalidRequestError:
            cls.db.session.rollback()
            cls.save(obj)

    def _create_model_object(self, *args):
        raise NotImplementedError

    @staticmethod
    def _exists_in_db(obj):
        raise NotImplementedError

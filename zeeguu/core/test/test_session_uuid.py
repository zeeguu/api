"""The collision guard in Session.create_for_user.

It used to read

    if cls.query.get(_uuid) is None:

which is a PRIMARY KEY lookup, and the primary key of session is the integer
id, not the uuid. So it asked whether a session existed whose *id* equalled a
32-char hex string -- never true -- and the loop never retried. A uuid4
collision is not plausible on its own, so this never mattered in practice; it
matters that the guard now actually guards.
"""

from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.model.db import db
from zeeguu.core.model.session import Session
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule


class SessionUuidTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user

    def test_create_for_user_gives_a_fresh_uuid(self):
        first = Session.create_for_user(self.user)
        db.session.add(first)
        db.session.commit()

        second = Session.create_for_user(self.user)

        assert first.uuid != second.uuid

    def test_create_for_user_retries_when_the_uuid_is_taken(self):
        taken = Session.create_for_user(self.user)
        db.session.add(taken)
        db.session.commit()

        # Hand out the existing uuid first: the guard has to notice and retry.
        class _Uuid:
            def __init__(self, hex_):
                self.hex = hex_

        with patch(
            "zeeguu.core.model.session.uuid.uuid4",
            side_effect=[_Uuid(taken.uuid), _Uuid("f" * 32)],
        ):
            fresh = Session.create_for_user(self.user)

        assert fresh.uuid == "f" * 32

    def test_find_returns_the_session_for_its_uuid(self):
        session_object = Session.create_for_user(self.user)
        db.session.add(session_object)
        db.session.commit()

        assert Session.find(session_object.uuid).id == session_object.id

    def test_find_returns_none_for_an_unknown_uuid(self):
        assert Session.find("e" * 32) is None

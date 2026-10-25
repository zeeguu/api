from contextlib import contextmanager
from unittest import mock

from sqlalchemy.orm import Query
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model.db import db
from zeeguu.core.model.domain_name import DomainName
from zeeguu.core.model.new_text import NewText
from zeeguu.core.model.source_text import SourceText
from zeeguu.core.model.url import Url
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule

session = db.session


@contextmanager
def first_lookup_of(cls_):
    """
    The first lookup of a `cls_` row misses, as it does on MySQL for the
    request that loses an insert race: it reads an older REPEATABLE READ
    snapshot, from before the other request committed the row.
    """
    real_one = Query.one
    real_one_or_none = Query.one_or_none
    missed = []

    def is_first_lookup(query):
        if missed or query.column_descriptions[0]["entity"] is not cls_:
            return False
        missed.append(query)
        return True

    def one(query):
        if is_first_lookup(query):
            raise NoResultFound()
        return real_one(query)

    def one_or_none(query):
        if is_first_lookup(query):
            return None
        return real_one_or_none(query)

    with mock.patch.object(Query, "one", one), mock.patch.object(
        Query, "one_or_none", one_or_none
    ):
        yield
    assert missed, f"no lookup of {cls_.__name__} was made"


class LegacyFindOrCreateRaceTest(ModelTestMixIn):
    """
    The loser of an insert race gets the winner's row, and keeps the work
    its caller had pending. These find_or_creates used to roll back the
    whole session when the insert failed, which threw that work away.
    """

    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        session.commit()

    def _caller_has_pending_work(self):
        self.user.name = "changed by the caller"

    def _assert_pending_work_survived(self):
        session.commit()
        session.refresh(self.user)
        assert self.user.name == "changed by the caller"

    def test_domain_name(self):
        url = "https://race.example.com/some/article"
        winner = DomainName.find_or_create(session, url)
        winner_id = winner.id
        self._caller_has_pending_work()

        with first_lookup_of(DomainName):
            loser = DomainName.find_or_create(session, url)

        assert loser.id == winner_id
        self._assert_pending_work_survived()
        assert (
            DomainName.query.filter_by(domain_name="https://race.example.com").count()
            == 1
        )

    def test_url(self):
        url = "https://race.example.com/some/article"
        winner = Url.find_or_create(session, url, "a title")
        winner_id = winner.id
        self._caller_has_pending_work()

        with first_lookup_of(Url):
            loser = Url.find_or_create(session, url, "a title")

        assert loser.id == winner_id
        self._assert_pending_work_survived()
        assert Url.query.filter_by(path="/some/article").count() == 1

    def test_url_with_a_path_over_255_chars_is_not_saved(self):
        url = "https://race.example.com/" + "a" * 300
        assert Url.find_or_create(session, url) is None

    def test_new_text(self):
        content = "A sentence that two requests save at the same time."
        winner = NewText.find_or_create(session, content)
        winner_id = winner.id
        self._caller_has_pending_work()

        with first_lookup_of(NewText):
            loser = NewText.find_or_create(session, content, commit=False)

        assert loser.id == winner_id
        self._assert_pending_work_survived()
        assert NewText.query.filter_by(content=content).count() == 1

    def test_source_text(self):
        content = "An article body that two requests save at the same time."
        winner = SourceText.find_or_create(session, content)
        winner_id = winner.id
        self._caller_has_pending_work()

        with first_lookup_of(SourceText):
            loser = SourceText.find_or_create(session, content, commit=False)

        assert loser.id == winner_id
        self._assert_pending_work_survived()
        assert SourceText.query.filter_by(content=content).count() == 1

    def test_text_rules_reuse_the_row_for_the_same_content(self):
        # content_hash is unique, so building a second row for the same text
        # would fail; the rules go through find_or_create instead.
        from zeeguu.core.test.rules.new_text_rule import NewTextRule
        from zeeguu.core.test.rules.source_text_rule import SourceTextRule

        assert NewTextRule("same text").text.id == NewTextRule("same text").text.id
        assert (
            SourceTextRule("same text").source_text.id
            == SourceTextRule("same text").source_text.id
        )

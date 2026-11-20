from datetime import datetime
from unittest import TestCase

from zeeguu.core.content_retriever import a0_dialogues
from zeeguu.core.llm_services.a0_article_dialogue import DialogueResult
from zeeguu.core.model import Language, db
from zeeguu.core.model.article_classification import ArticleClassification
from zeeguu.core.model.article_dialogue import ArticleDialogue
from zeeguu.core.model.article_topic_map import TopicOriginType
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.topic_rule import TopicRule

OFF_PEAK = datetime(2026, 11, 18, 12, 0)  # a Wednesday, noon UTC
PEAK = datetime(2026, 11, 18, 7, 0)
SPORTS, CULTURE = 1, 2

LINES = [("Mette", "Hej."), ("Jens", "Hej, Mette."), ("Mette", "Se her!"), ("Jens", "Hvad er det?")]


class FakeWriter:
    def __init__(self, accept=True):
        self.calls, self.accept = [], accept

    def __call__(self, language_name, title, summary):
        self.calls.append(title)
        if not self.accept:
            return DialogueResult(skip_reason="did not pass")
        return DialogueResult(title="En dialog", lines=LINES)


class A0DialoguesAtCrawlTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.danish = Language.find_or_create("da")
        self.before = a0_dialogues.last_article_id(db.session)

    def evergreen(self, topic_id=SPORTS, language=None):
        article = ArticleRule().article
        article.language = language or self.danish
        article.article_type = "general"
        article.add_topic_if_doesnt_exist(TopicRule.get_or_create_topic(topic_id), db.session, TopicOriginType.HARDSET)
        db.session.commit()
        return article

    def run_step(self, writer, now=OFF_PEAK, language=None):
        return a0_dialogues.write_for_new_evergreen(
            db.session, language or self.danish, self.before, now_utc=now, write=writer
        )

    def test_a_new_danish_evergreen_article_gets_a_dialogue(self):
        article = self.evergreen()

        saved = self.run_step(FakeWriter())

        assert [d.inspired_by_article_id for d in saved] == [article.id]

    def test_at_most_three_per_topic_a_day(self):
        for _ in range(4):
            self.evergreen(SPORTS)
        culture = self.evergreen(CULTURE)
        writer = FakeWriter()

        saved = self.run_step(writer)

        assert len(saved) == 4  # 3 sports + 1 culture
        assert culture.id in {d.inspired_by_article_id for d in saved}
        assert len(writer.calls) == 4  # the fourth sports article was never written

    def test_the_topic_cap_counts_the_dialogues_already_written_today(self):
        for _ in range(2):
            self.evergreen(SPORTS)
        self.run_step(FakeWriter())
        self.before = a0_dialogues.last_article_id(db.session)
        for _ in range(2):
            self.evergreen(SPORTS)

        assert len(self.run_step(FakeWriter())) == 1

    def test_at_most_per_run_per_crawl(self):
        for topic in range(1, 9):
            self.evergreen(topic)

        assert len(self.run_step(FakeWriter())) == a0_dialogues.PER_RUN

    def test_nothing_at_a_deepseek_peak_hour(self):
        self.evergreen()
        writer = FakeWriter()

        assert self.run_step(writer, now=PEAK) == []
        assert writer.calls == []

    def test_weekends_have_no_peak(self):
        assert not a0_dialogues.is_deepseek_peak(datetime(2026, 11, 21, 7, 0))  # Saturday
        assert a0_dialogues.is_deepseek_peak(datetime(2026, 11, 20, 2, 30))  # Friday

    def test_only_articles_from_this_crawl(self):
        self.evergreen()
        self.before = a0_dialogues.last_article_id(db.session)
        writer = FakeWriter()

        assert self.run_step(writer) == []
        assert writer.calls == []

    def test_a_dropped_dialogue_saves_nothing(self):
        self.evergreen()

        assert self.run_step(FakeWriter(accept=False)) == []
        assert ArticleDialogue.query.count() == 0

    def test_not_for_other_languages(self):
        german = Language.find_or_create("de")
        self.evergreen(language=german)
        writer = FakeWriter()

        assert self.run_step(writer, language=german) == []
        assert writer.calls == []

    def test_news_and_disturbing_articles_are_skipped(self):
        news = self.evergreen()
        news.article_type = "news"
        disturbing = self.evergreen(CULTURE)
        ArticleClassification.find_or_create(db.session, disturbing, "DISTURBING", "KEYWORD")
        db.session.commit()
        writer = FakeWriter()

        assert self.run_step(writer) == []
        assert writer.calls == []

from unittest import TestCase

from zeeguu.core.test.model_test_mixin import ModelTestMixIn

import zeeguu.core
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.user_article_rule import UserArticleRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.model.user_article import UserArticle
from zeeguu.core.model.personal_copy import PersonalCopy

db_session = zeeguu.core.model.db.session


class UserArticleTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()

        self.user_article = UserArticleRule().user_article
        self.user = self.user_article.user
        self.article = self.user_article.article

    def test_article_is_not_starred_initially(self):
        assert not self.user_article.starred

    def test_all_starred_articles(self):
        self.article.star_for_user(db_session, self.user)
        assert 1 == len(UserArticle.all_starred_articles_of_user(self.user))

    def test_all_starred_or_liked_articles(self):
        self.article.star_for_user(db_session, self.user)
        assert 1 == len(UserArticle.all_starred_or_liked_articles_of_user(self.user))

    def test_my_articles_returns_personal_copies(self):
        # A PersonalCopy is enough to appear in My Articles — even without
        # a UserArticle row (i.e. user saved via Send-to-Zeeguu but hasn't
        # opened it yet). PersonalCopy.all_for() filters by learned_language,
        # so align the article's language with the user's.
        self.article.language = self.user.learned_language
        db_session.add(self.article)
        db_session.commit()
        PersonalCopy.make_for(self.user, self.article, db_session)
        infos = UserArticle.my_articles_info(self.user)
        assert 1 == len(infos)
        assert self.article.id == infos[0]["id"]

    def test_my_articles_is_empty_without_personal_copies(self):
        # Stars and likes are NOT in scope for My Articles — this tab is
        # for explicit saves only.
        self.article.star_for_user(db_session, self.user)
        assert [] == UserArticle.my_articles_info(self.user)

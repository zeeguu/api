"""
Which children of an article may be offered as a *level* of it.

Two things hang off parent_article_id: same-language level adaptations, and the
translated copy a friend-share makes for a recipient learning another language.
Only the first kind is a level of this article — the second is a legitimately
foreign-language article that happens to share a parent, and handing it to a
learner of the parent's language is a silent language failure of exactly the kind
zeeguu.core.language.language_check exists to prevent.
"""
from unittest import TestCase

import zeeguu.core
from zeeguu.core.model.article import MARKED_BROKEN_DUE_TO_LOW_QUALITY
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.language_rule import LanguageRule

session = zeeguu.core.model.db.session


class UsableSimplifiedVersionsTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.original = ArticleRule().article

    def _child(self, language, cefr_level="A2"):
        child = ArticleRule().article
        child.parent_article_id = self.original.id
        child.language = language
        child.cefr_level = cefr_level
        session.add(child)
        session.commit()
        return child

    def _another_language(self):
        language = LanguageRule().random
        while language.id == self.original.language_id:
            language = LanguageRule().random
        return language

    def test_a_same_language_child_is_a_level_of_the_article(self):
        child = self._child(self.original.language)
        assert child in self.original.usable_simplified_versions

    def test_a_friend_share_translation_is_not_a_level_of_the_article(self):
        translated = self._child(self._another_language())
        assert translated in self.original.simplified_versions
        assert translated not in self.original.usable_simplified_versions

    def test_a_child_marked_broken_is_not_offered(self):
        child = self._child(self.original.language)
        child.broken = MARKED_BROKEN_DUE_TO_LOW_QUALITY
        session.add(child)
        session.commit()
        assert child not in self.original.usable_simplified_versions

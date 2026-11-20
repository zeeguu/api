from unittest import TestCase

import pytest

from zeeguu.core.model import db
from zeeguu.core.model.article_dialogue import ArticleDialogue
from zeeguu.core.model.article_fragment import ArticleFragment
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule

LINES = [
    ("Mette", "Se! Kim har lavet en ny app."),
    ("Jens", "En app? Hvad skal den?"),
    ("Mette", "Den skal skræmme ulven væk."),
    ("Jens", "Hvorfor lavede Kim appen?"),
]
WRITER = ("claude-sonnet-5-5", "a0-article-dialogue-v1")
CHECKER = ("claude-opus-5-5", "a0-article-dialogue-check-v1")


class ArticleDialogueTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.inspiring = ArticleRule().article

    def _create(self, lines=LINES):
        dialogue = ArticleDialogue.create(db.session, self.inspiring, "En app mod ulven", lines, WRITER, CHECKER)
        db.session.commit()
        return dialogue

    def test_each_line_is_one_fragment_in_the_speakers_order(self):
        dialogue = self._create()

        fragments = list(ArticleFragment.get_all_article_fragments_in_order(dialogue.article_id))
        assert [f.text.content for f in fragments] == [text for _, text in LINES]
        assert dialogue.speakers == [speaker for speaker, _ in LINES]
        assert dialogue.article.get_content() == "\n\n".join(text for _, text in LINES)

    def test_the_dialogue_is_not_a_simplification_of_the_article(self):
        dialogue = self._create()

        assert dialogue.article.parent_article_id is None
        assert dialogue.article not in self.inspiring.simplified_versions
        assert "is_simplified" not in dialogue.article.article_info()
        assert dialogue.article.article_type is None  # so not in the Evergreen pool itself

    def test_info_names_the_speakers_and_the_inspiring_article(self):
        info = self._create().info()

        assert info["speakers"] == ["Mette", "Jens", "Mette", "Jens"]
        assert info["inspired_by"]["id"] == self.inspiring.id
        assert info["inspired_by"]["title"] == self.inspiring.title

    def test_writer_and_checker_are_recorded(self):
        dialogue = self._create()

        assert (dialogue.writer_ai_generator.model_name, dialogue.writer_ai_generator.prompt_version) == WRITER
        assert (dialogue.checker_ai_generator.model_name, dialogue.checker_ai_generator.prompt_version) == CHECKER

    def test_a_line_that_would_split_is_refused(self):
        with pytest.raises(ValueError):
            self._create([("Mette", "Hej.\n\nHvordan går det?"), ("Jens", "Godt.")])

    def test_an_empty_line_is_refused(self):
        with pytest.raises(ValueError):
            self._create([("Mette", "Hej."), ("Jens", "  ")])

    def test_finding_which_articles_have_a_dialogue(self):
        dialogue = self._create()
        other = ArticleRule().article

        assert ArticleDialogue.article_ids_inspired_by([self.inspiring.id, other.id]) == {
            self.inspiring.id: dialogue.article_id
        }

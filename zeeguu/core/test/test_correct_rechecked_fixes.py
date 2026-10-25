"""correct_past_fix (tools/correct_rechecked_fixes.py) moves only the learner's bookmark in the
fix's sentence, and leaves the fixed meaning as it is for everyone else."""
from unittest import TestCase

import zeeguu.core
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.model.language import Language
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord
from zeeguu.core.model.validation_log import ValidationLog
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session
SENTENCE = "De son côté, la France demande une motion."


class CorrectRecheckedFixesTest(ModelTestMixIn, TestCase):
    def _bookmark(self, user, translation_source="reading", sentence=SENTENCE):
        return Bookmark.find_or_create(
            session, user, "côté", user.learned_language.code, "kant", user.native_language.code, sentence,
            None, None, sentence_i=0, token_i=2, total_tokens=1, c_sentence_i=0, c_token_i=0,
            context_identifier=ContextIdentifier(context_type=ContextType.USER_EDITED_TEXT),
            translation_source=translation_source,
        )

    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        # French -> Dutch as in the real cases; a random language can lack tokenizer data here
        self.user.learned_language, self.user.native_language = Language.find_or_create("fr"), Language.find_or_create("nl")
        session.add(self.user)
        learned, native = self.user.learned_language.code, self.user.native_language.code
        self.bookmark = Bookmark.find_or_create(
            session, self.user, "côté", learned, "kant", native, SENTENCE, None, None,
            sentence_i=0, token_i=2, total_tokens=1, c_sentence_i=0, c_token_i=0,
            context_identifier=ContextIdentifier(context_type=ContextType.USER_EDITED_TEXT),
            translation_source="reading",
        )
        self.fixed = self.bookmark.user_word.meaning
        self.fixed.validated = Meaning.VALID
        self.fix = ValidationLog.log_fixed(session, old_meaning=self.fixed, new_meaning=self.fixed, context=SENTENCE)
        session.add(self.fixed)
        session.commit()

    def test_the_bookmark_moves_and_the_fixed_meaning_stays(self):
        from zeeguu.core.bookmark_operations import correct_past_fix as tool

        [bookmark] = tool.learners_bookmarks(self.fix)
        new_user_word = tool.move(session, bookmark, self.fix, "de son côté", "van zijn kant", "de son côté = van zijn kant")
        session.commit()

        bookmark = session.get(Bookmark, self.bookmark.id)
        self.assertEqual(bookmark.user_word_id, new_user_word.id)
        self.assertEqual(new_user_word.meaning.origin.content, "de son côté")
        self.assertEqual(new_user_word.meaning.translation.content, "van zijn kant")
        self.assertEqual((bookmark.token_i, bookmark.total_tokens), (0, 3))  # placed on "De son côté", whatever the case
        self.assertEqual(session.get(Meaning, self.fixed.id).validated, Meaning.VALID)  # others keep it
        self.assertEqual(ValidationLog.query.filter_by(new_meaning_id=new_user_word.meaning_id).count(), 1)

    def test_a_generated_example_is_not_corrected(self):
        from zeeguu.core.bookmark_operations import correct_past_fix as tool

        self.bookmark.translation_source = "generated_example"
        session.add(self.bookmark)
        session.commit()
        self.assertEqual(tool.learners_bookmarks(self.fix), [])

    def test_another_learner_with_the_pair_in_the_sentence_is_corrected_too(self):
        # the pair is wrong in that sentence, whoever has it there
        from zeeguu.core.bookmark_operations import correct_past_fix as tool

        other = UserRule().user
        other.learned_language, other.native_language = self.user.learned_language, self.user.native_language
        session.add(other)
        session.commit()
        theirs = self._bookmark(other)

        self.assertEqual(sorted(b.id for b in tool.learners_bookmarks(self.fix)), sorted([self.bookmark.id, theirs.id]))

    def test_a_card_that_is_the_fixed_meaning_is_not_applied(self):
        from zeeguu.core.bookmark_operations import correct_past_fix as tool

        self.assertIn("fixed meaning", tool.why_not(self.fix, "Côté", "Kant"))
        self.assertIsNone(tool.why_not(self.fix, "de son côté", "van zijn kant"))
        self.assertIn("not a validator fix", tool.why_not(None, "x", "y"))

    def test_progress_goes_along_when_the_rest_are_generated_examples(self):
        from zeeguu.core.bookmark_operations import correct_past_fix as tool

        user_word = self.bookmark.user_word
        user_word.fit_for_study = True  # progress is kept only for a word in study
        FourLevelsPerWord.find_or_create(session, user_word)  # sets level 1
        user_word.level = 2
        session.add(user_word)
        example = self._bookmark(self.user, "generated_example", "Le côté droit de la rue est vide.")
        session.commit()
        self.assertEqual(example.user_word_id, user_word.id)

        [bookmark] = tool.learners_bookmarks(self.fix)
        new_user_word = tool.move(session, bookmark, self.fix, "de son côté", "van zijn kant", "de son côté = van zijn kant")
        session.commit()

        self.assertEqual(new_user_word.level, 2)

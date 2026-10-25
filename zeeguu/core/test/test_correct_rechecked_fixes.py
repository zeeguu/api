"""correct_past_fix (tools/correct_rechecked_fixes.py) moves only the learner's bookmark in the
fix's sentence, and leaves the fixed meaning as it is for everyone else."""
from unittest import TestCase

import zeeguu.core
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.validation_log import ValidationLog
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session
SENTENCE = "De son côté, la France demande une motion."


class CorrectRecheckedFixesTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
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
        new_user_word = tool.move(session, bookmark, self.fix, "De son côté", "van zijn kant", "De son côté = van zijn kant")
        session.commit()

        bookmark = session.get(Bookmark, self.bookmark.id)
        self.assertEqual(bookmark.user_word_id, new_user_word.id)
        self.assertEqual(new_user_word.meaning.origin.content, "De son côté")
        self.assertEqual(new_user_word.meaning.translation.content, "van zijn kant")
        self.assertEqual((bookmark.token_i, bookmark.total_tokens), (0, 3))  # placed on "De son côté"
        self.assertEqual(session.get(Meaning, self.fixed.id).validated, Meaning.VALID)  # others keep it
        self.assertEqual(ValidationLog.query.filter_by(new_meaning_id=new_user_word.meaning_id).count(), 1)

    def test_a_generated_example_is_not_corrected(self):
        from zeeguu.core.bookmark_operations import correct_past_fix as tool

        self.bookmark.translation_source = "generated_example"
        session.add(self.bookmark)
        session.commit()
        self.assertEqual(tool.learners_bookmarks(self.fix), [])

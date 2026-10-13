from unittest.mock import patch

import zeeguu.core
from zeeguu.core.account_management import user_account_merge
from zeeguu.core.account_management.user_account_merge import (
    MergeError,
    check_policies_cover_schema,
    merge_users,
    _inspector,
)
from zeeguu.core.model import (
    Bookmark,
    Friendship,
    Teacher,
    User,
    UserCohortMap,
    UserLanguage,
    UserPreference,
    UserWord,
)
from zeeguu.core.model.language import Language
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.cohort_rule import CohortRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.test.rules.user_word_rule import UserWordRule
from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord

session = zeeguu.core.model.db.session


def quiet(*args):
    pass


class UserAccountMergeTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()
        self.source_rule = UserRule()
        self.target_rule = UserRule()
        self.source = self.source_rule.user
        self.target = self.target_rule.user
        # both learn the same language, as the duplicate accounts in prod do
        self.source.learned_language = self.target.learned_language
        session.commit()

    def merge(self, **kwargs):
        report = merge_users(self.source, self.target, log=quiet, **kwargs)
        session.commit()
        session.expire_all()
        return report

    def words(self, user):
        return UserWord.query.filter_by(user_id=user.id).all()

    def test_every_user_reference_in_the_schema_has_a_policy(self):
        # Fails when a new table referencing user (or user_word) is added
        # without telling the merge what to do with it.
        check_policies_cover_schema(_inspector())

    def test_refuses_to_run_when_a_reference_has_no_policy(self):
        policies = dict(user_account_merge.POLICIES)
        del policies[("user_article", "user_id")]
        with patch.object(user_account_merge, "POLICIES", policies):
            with self.assertRaises(MergeError) as e:
                merge_users(self.source, self.target, log=quiet)
        self.assertIn("user_article.user_id", str(e.exception))

    def test_distinct_words_and_their_bookmarks_move(self):
        self.source_rule.add_bookmarks(3)
        self.target_rule.add_bookmarks(2)

        self.merge()

        self.assertEqual(5, len(self.words(self.target)))
        self.assertEqual(0, len(self.words(self.source)))
        self.assertEqual(5, len(Bookmark.find_by_specific_user(self.target)))

    def test_same_meaning_is_merged_into_the_richer_row(self):
        source_bookmark = BookmarkRule(self.source).bookmark
        meaning = source_bookmark.user_word.meaning
        target_word = UserWordRule(self.target, meaning).user_word
        target_bookmark = BookmarkRule(self.target).bookmark
        target_bookmark.user_word = target_word
        session.commit()

        source_word = source_bookmark.user_word
        FourLevelsPerWord.find_or_create(session, source_word)
        FourLevelsPerWord.find_or_create(session, target_word)
        source_word.level = 3  # after find_or_create, which resets it to 1
        session.commit()
        source_word_id, target_word_id = source_word.id, target_word.id

        report = self.merge()

        words = [w for w in self.words(self.target) if w.meaning_id == meaning.id]
        self.assertEqual(1, len(words))
        self.assertEqual(source_word_id, words[0].id)
        self.assertIsNone(UserWord.query.get(target_word_id))
        self.assertEqual(
            {source_bookmark.id, target_bookmark.id},
            {b.id for b in Bookmark.query.filter_by(user_word_id=source_word_id)},
        )
        self.assertEqual(1, report["user_word.user_id"]["collisions, source row kept"])

    def test_tie_keeps_the_targets_row(self):
        source_word = BookmarkRule(self.source).bookmark.user_word
        target_word = UserWordRule(self.target, source_word.meaning).user_word
        target_bookmark = BookmarkRule(self.target).bookmark
        target_bookmark.user_word = target_word
        session.commit()
        target_word_id, meaning_id = target_word.id, source_word.meaning_id

        self.merge()

        words = [w for w in self.words(self.target) if w.meaning_id == meaning_id]
        self.assertEqual([target_word_id], [w.id for w in words])

    def test_languages_the_target_lacks_move_and_shared_ones_stay(self):
        shared = self.target.learned_language
        other = Language.find_or_create("fr" if shared.code != "fr" else "de")
        UserLanguage.find_or_create(session, self.target, shared).cefr_level = 4
        UserLanguage.find_or_create(session, self.source, shared).cefr_level = 1
        UserLanguage.find_or_create(session, self.source, other)
        session.commit()

        self.merge()

        target_languages = {
            ul.language_id: ul for ul in UserLanguage.query.filter_by(user_id=self.target.id)
        }
        self.assertEqual({shared.id, other.id}, set(target_languages))
        self.assertEqual(4, target_languages[shared.id].cefr_level)

    def test_classes_are_joined_once_and_teacher_rights_move(self):
        both = CohortRule().cohort
        only_source = CohortRule().cohort
        session.add_all(
            [
                UserCohortMap(user=self.source, cohort=both),
                UserCohortMap(user=self.target, cohort=both),
                UserCohortMap(user=self.source, cohort=only_source),
                Teacher(self.source),
            ]
        )
        session.commit()

        self.merge()

        self.assertEqual(
            {both.id, only_source.id},
            {m.cohort_id for m in UserCohortMap.query.filter_by(user_id=self.target.id)},
        )
        self.assertEqual(0, UserCohortMap.query.filter_by(user_id=self.source.id).count())
        self.assertEqual(1, Teacher.query.filter_by(user_id=self.target.id).count())

    def test_target_wins_a_preference_both_have(self):
        UserPreference.find_or_create(session, self.source, "audio_speed", "fast")
        UserPreference.find_or_create(session, self.target, "audio_speed", "slow")
        UserPreference.find_or_create(session, self.source, "only_on_source", "yes")
        session.commit()

        self.merge()

        prefs = {
            p.key: p.value for p in UserPreference.query.filter_by(user_id=self.target.id)
        }
        self.assertEqual("slow", prefs["audio_speed"])
        self.assertEqual("yes", prefs["only_on_source"])

    def test_friendships_are_moved_and_deduplicated(self):
        both_know = UserRule().user
        only_source_knows = UserRule().user
        session.add_all(
            [
                Friendship(self.source.id, self.target.id),
                Friendship(self.source.id, both_know.id),
                Friendship(both_know.id, self.target.id),
                Friendship(only_source_knows.id, self.source.id),
            ]
        )
        session.commit()

        self.merge()

        friends = Friendship.query.filter(
            (Friendship.user_a_id == self.target.id) | (Friendship.user_b_id == self.target.id)
        ).all()
        partners = sorted(f.user_a_id if f.user_b_id == self.target.id else f.user_b_id for f in friends)
        self.assertEqual(sorted([both_know.id, only_source_knows.id]), partners)
        self.assertEqual(
            0,
            Friendship.query.filter(
                (Friendship.user_a_id == self.source.id) | (Friendship.user_b_id == self.source.id)
            ).count(),
        )

    def test_source_is_deactivated_not_deleted(self):
        source_id, source_email = self.source.id, self.source.email
        self.source.update_password("known-password")
        session.commit()

        self.merge()

        source = User.find_by_id(source_id)
        self.assertIsNotNone(source)
        self.assertTrue(source.email.endswith("@merged.zeeguu.invalid"))
        self.assertIn(f"merged into {self.target.id}", source.name)
        self.assertIsNone(User.authorize(source.email, "known-password"))
        self.assertNotEqual(source_email, User.find_by_id(self.target.id).email)

    def test_take_email_gives_the_target_the_sources_address(self):
        source_email = self.source.email

        self.merge(take_email=True)

        target = User.find_by_id(self.target.id)
        self.assertEqual(source_email, target.email)
        self.assertFalse(target.email_verified)

    def test_merging_twice_is_refused(self):
        self.merge()
        with self.assertRaises(MergeError):
            merge_users(self.source, UserRule().user, log=quiet)

    def test_dry_run_rollback_leaves_everything_in_place(self):
        self.source_rule.add_bookmarks(2)
        email = self.source.email
        # pysqlite only opens a transaction before DML, so a merge that starts
        # with a SAVEPOINT would RELEASE (commit) it. MySQL, where the tool
        # runs, always has one open. A flushed write puts sqlite in the same state.
        self.target.name = self.target.name + " "
        session.flush()

        merge_users(self.source, self.target, log=quiet)
        session.rollback()
        session.expire_all()

        self.assertEqual(2, len(self.words(User.find_by_id(self.source.id))))
        self.assertEqual(email, User.find_by_id(self.source.id).email)

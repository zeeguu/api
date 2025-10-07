"""
Tests for user article broken reporting system.

Tests verify:
- Regular user reports (threshold = 2)
- Teacher reports (immediate marking)
- Duplicate prevention
- Report retrieval
"""

from unittest import TestCase

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.user_rule import UserRule

from zeeguu.core.model import Article, User, UserArticleBrokenReport, db
from zeeguu.core.model.article_broken_code_map import ArticleBrokenMap, LowQualityTypes
from zeeguu.core.model import Teacher


class UserArticleBrokenReportTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()

        # Create test article
        self.article = ArticleRule().article

        # Create test users
        self.user1 = UserRule().user
        self.user2 = UserRule().user
        self.user3 = UserRule().user

        # Make user3 a teacher
        self.teacher = Teacher(self.user3)
        db.session.add(self.teacher)
        db.session.commit()

    def test_single_regular_user_report_does_not_mark_as_broken(self):
        """First regular user report should NOT mark article as broken."""
        report, marked = UserArticleBrokenReport.create(
            db.session, self.user1, self.article, "Article has paywall"
        )

        count = UserArticleBrokenReport.count_for_article(db.session, self.article)

        self.assertEqual(count, 1)
        self.assertFalse(marked)
        self.assertEqual(self.article.broken, 0)

    def test_two_regular_users_mark_as_broken(self):
        """Second regular user report SHOULD mark article as broken (threshold=2)."""
        # First report
        report1, marked1 = UserArticleBrokenReport.create(
            db.session, self.user1, self.article, "Article has paywall"
        )
        self.assertFalse(marked1)

        # Second report - threshold reached!
        report2, marked2 = UserArticleBrokenReport.create(
            db.session, self.user2, self.article, "Content is incomplete"
        )

        count = UserArticleBrokenReport.count_for_article(db.session, self.article)

        self.assertEqual(count, 2)
        self.assertTrue(marked2)
        self.assertEqual(self.article.broken, 100)  # MARKED_BROKEN_DUE_TO_LOW_QUALITY

        # Verify USER_REPORTED code exists
        broken_mark = ArticleBrokenMap.query.filter(
            ArticleBrokenMap.article_id == self.article.id,
            ArticleBrokenMap.broken_code == LowQualityTypes.USER_REPORTED
        ).first()

        self.assertIsNotNone(broken_mark)

    def test_teacher_marks_immediately(self):
        """Teacher report should mark article as broken immediately."""
        report, marked = UserArticleBrokenReport.create(
            db.session, self.user3, self.article, "Teacher found issue"
        )

        count = UserArticleBrokenReport.count_for_article(db.session, self.article)

        self.assertEqual(count, 1)
        self.assertTrue(marked)  # Teacher marks immediately!
        self.assertEqual(self.article.broken, 100)

        # Verify USER_REPORTED code exists
        broken_mark = ArticleBrokenMap.query.filter(
            ArticleBrokenMap.article_id == self.article.id,
            ArticleBrokenMap.broken_code == LowQualityTypes.USER_REPORTED
        ).first()

        self.assertIsNotNone(broken_mark)

    def test_duplicate_report_prevention(self):
        """Same user cannot report the same article twice."""
        # First report
        report1, marked1 = UserArticleBrokenReport.create(
            db.session, self.user1, self.article, "First report"
        )

        # Duplicate report
        report2, marked2 = UserArticleBrokenReport.create(
            db.session, self.user1, self.article, "Duplicate report"
        )

        count = UserArticleBrokenReport.count_for_article(db.session, self.article)

        self.assertEqual(count, 1)  # Should still be 1
        self.assertEqual(report1.id, report2.id)  # Same report object returned
        self.assertFalse(marked2)  # No marking on duplicate

    def test_retrieve_all_reports_for_article(self):
        """Can retrieve all reports for an article."""
        # Create multiple reports
        UserArticleBrokenReport.create(
            db.session, self.user1, self.article, "Reason 1"
        )
        UserArticleBrokenReport.create(
            db.session, self.user2, self.article, "Reason 2"
        )

        reports = UserArticleBrokenReport.all_for_article(db.session, self.article)

        self.assertEqual(len(reports), 2)
        reasons = [r.reason for r in reports]
        self.assertIn("Reason 1", reasons)
        self.assertIn("Reason 2", reasons)

    def test_retrieve_all_reports_for_user(self):
        """Can retrieve all reports by a user."""
        article2 = ArticleRule().article

        # User reports 2 different articles
        UserArticleBrokenReport.create(
            db.session, self.user1, self.article, "Report 1"
        )
        UserArticleBrokenReport.create(
            db.session, self.user1, article2, "Report 2"
        )

        reports = UserArticleBrokenReport.all_for_user(db.session, self.user1)

        self.assertEqual(len(reports), 2)
        article_ids = [r.article_id for r in reports]
        self.assertIn(self.article.id, article_ids)
        self.assertIn(article2.id, article_ids)

    def test_find_existing_report(self):
        """Can find existing report by user and article."""
        # Create report
        created_report, _ = UserArticleBrokenReport.create(
            db.session, self.user1, self.article, "Test reason"
        )

        # Find it
        found_report = UserArticleBrokenReport.find(
            db.session, self.user1, self.article
        )

        self.assertIsNotNone(found_report)
        self.assertEqual(found_report.id, created_report.id)
        self.assertEqual(found_report.reason, "Test reason")

    def test_find_nonexistent_report_returns_none(self):
        """Finding nonexistent report returns None."""
        found = UserArticleBrokenReport.find(
            db.session, self.user1, self.article
        )

        self.assertIsNone(found)

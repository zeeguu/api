"""Race-guard behaviour for the bookmark/context join tables.

Every one of these join models carries a copy-pasted find_or_create that used to
(a) swallow the wrong exception ('except A or B' only ever caught NoResultFound)
and (b) have no unique key, so a concurrent first-open race could create two rows
for the same (bookmark, anchor) -- which later broke find_by_bookmark/.one() with
MultipleResultsFound.

These tests mirror test_article_level_summary.py's
test_context_find_or_create_is_idempotent / _rejected_by_unique_constraint, run
across all six affected models at once:

    ArticleSummaryContext, ArticleFragmentContext, ArticleTitleContext,
    VideoTitleContext, VideoCaptionContext, ExampleSentenceContext
"""
from unittest import TestCase

from sqlalchemy.exc import IntegrityError

import zeeguu.core
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.meaning_rule import MeaningRule
from zeeguu.core.test.rules.user_rule import UserRule

from zeeguu.core.model.article_fragment import ArticleFragment
from zeeguu.core.model.article_fragment_context import ArticleFragmentContext
from zeeguu.core.model.article_summary_context import ArticleSummaryContext
from zeeguu.core.model.article_title_context import ArticleTitleContext
from zeeguu.core.model.caption import Caption
from zeeguu.core.model.example_sentence import ExampleSentence
from zeeguu.core.model.example_sentence_context import ExampleSentenceContext
from zeeguu.core.model.new_text import NewText
from zeeguu.core.model.video import Video
from zeeguu.core.model.video_caption_context import VideoCaptionContext
from zeeguu.core.model.video_title_context import VideoTitleContext

session = zeeguu.core.model.db.session


class BookmarkContextUniquenessTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.article = ArticleRule().article
        language = self.user.learned_language

        self.fragment = ArticleFragment.find_or_create(
            session, self.article, "a fragment of text", 0
        )

        self.video = Video(
            video_unique_key="test_video_key",
            title="a test video",
            source=None,
            description="a description",
            published_time=None,
            channel=None,
            thumbnail_url=None,
            duration=0,
            language=language,
        )
        session.add(self.video)

        self.caption = Caption(
            self.video, 0, 1000, NewText.find_or_create(session, "a caption line")
        )
        session.add(self.caption)

        self.example_sentence = ExampleSentence(
            "an example sentence", language, MeaningRule().meaning
        )
        session.add(self.example_sentence)
        session.commit()

    def _cases(self):
        """(label, ContextClass, find_or_create-args, anchor filter kwargs)."""
        return [
            (
                "article_summary",
                ArticleSummaryContext,
                (self.article,),
                dict(article_id=self.article.id),
            ),
            (
                "article_title",
                ArticleTitleContext,
                (self.article,),
                dict(article_id=self.article.id),
            ),
            (
                "article_fragment",
                ArticleFragmentContext,
                (self.fragment,),
                dict(article_fragment_id=self.fragment.id),
            ),
            (
                "video_title",
                VideoTitleContext,
                (self.video,),
                dict(video_id=self.video.id),
            ),
            (
                "video_caption",
                VideoCaptionContext,
                (self.caption,),
                dict(caption_id=self.caption.id),
            ),
            (
                "example_sentence",
                ExampleSentenceContext,
                (self.example_sentence,),
                dict(example_sentence_id=self.example_sentence.id),
            ),
        ]

    def test_context_find_or_create_is_idempotent(self):
        for label, ctx_cls, anchor_args, anchor_filter in self._cases():
            with self.subTest(context=label):
                bookmark = BookmarkRule(self.user).bookmark

                c1 = ctx_cls.find_or_create(session, bookmark, *anchor_args)
                c2 = ctx_cls.find_or_create(session, bookmark, *anchor_args)

                assert c1.id == c2.id
                count = ctx_cls.query.filter_by(
                    bookmark_id=bookmark.id, **anchor_filter
                ).count()
                assert count == 1

    def test_duplicate_context_rejected_by_unique_constraint(self):
        for label, ctx_cls, anchor_args, _ in self._cases():
            with self.subTest(context=label):
                bookmark = BookmarkRule(self.user).bookmark

                # Two raw rows for the same (bookmark, anchor) must not coexist.
                session.add(ctx_cls(bookmark, *anchor_args))
                session.add(ctx_cls(bookmark, *anchor_args))
                with self.assertRaises(IntegrityError):
                    session.flush()
                session.rollback()

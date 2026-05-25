import sqlalchemy
from zeeguu.core.model import (
    User,
    ArticleDifficultyFeedback,
    PersonalCopy,
    SearchFilter,
    UserPreference,
    UserCohortMap,
    UserWord,
    Friendship,
    FriendRequest,
    UserAvatar,
    UserBadge,
    UserBadgeProgress
)

import time
import zeeguu.core
from zeeguu.core.model.starred_article import StarredArticle

db_session = zeeguu.core.model.db.session

from zeeguu.core.model import (
    SearchSubscription,
    Teacher,
    TeacherCohortMap,
    Session,
    User,
    UserActivityData,
    Bookmark,
    UserArticle,
    UserReadingSession,
    UserExerciseSession,
)
from zeeguu.core.model import Article
from zeeguu.core.model.exercise import Exercise
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
from zeeguu.core.model.audio_lesson_generation_progress import AudioLessonGenerationProgress
from zeeguu.core.model.user_word_interaction_history import UserWordInteractionHistory
from zeeguu.core.model.example_sentence_context import ExampleSentenceContext
from zeeguu.core.model.article_summary_context import ArticleSummaryContext
from zeeguu.core.model.article_fragment_context import ArticleFragmentContext
from zeeguu.core.model.article_title_context import ArticleTitleContext
from zeeguu.core.model.video_caption_context import VideoCaptionContext
from zeeguu.core.model.video_title_context import VideoTitleContext
from zeeguu.core.model.translation_search import TranslationSearch
from zeeguu.core.model.user_article_broken_report import UserArticleBrokenReport
from zeeguu.core.model.article_topic_user_feedback import ArticleTopicUserFeedback
from zeeguu.core.model.user_language import UserLanguage
from zeeguu.core.model.user_video import UserVideo
from zeeguu.core.model.user_browsing_session import UserBrowsingSession
from zeeguu.core.model.user_notification import UserNotification
from zeeguu.core.model.meaning_report import MeaningReport
from zeeguu.core.model.user_onboarding_message import UserOnboardingMessage
from zeeguu.core.model.user_mwe_override import UserMweOverride
from zeeguu.core.model.topic_subscription import TopicSubscription
from zeeguu.core.model.exercise_report import ExerciseReport
from zeeguu.core.model.topic_filter import TopicFilter
from zeeguu.core.model.user_listening_session import UserListeningSession
from zeeguu.core.model.article_upload import ArticleUpload
from zeeguu.core.model.user_watching_session import UserWatchingSession
from zeeguu.core.model.user_feedback import UserFeedback
from zeeguu.core.model.example_sentence import ExampleSentence

# Tables with a NOT NULL FK to Bookmark; rows here must be deleted before
# the parent bookmark is removed.
bookmark_context_tables = [
    ExampleSentenceContext,
    ArticleSummaryContext,
    ArticleFragmentContext,
    ArticleTitleContext,
    VideoCaptionContext,
    VideoTitleContext,
    ExerciseReport,
]

tables_to_modify = [
    TranslationSearch,
    UserArticleBrokenReport,
    ArticleTopicUserFeedback,
    UserLanguage,
    UserVideo,
    UserBrowsingSession,
    UserNotification,
    MeaningReport,
    UserOnboardingMessage,
    UserMweOverride,
    TopicSubscription,
    ExerciseReport,
    TopicFilter,
    UserListeningSession,
    ArticleUpload,
    UserWatchingSession,
    UserFeedback,
    SearchSubscription,
    Session,
    Teacher,
    TeacherCohortMap,
    DailyAudioLesson,
    AudioLessonGenerationProgress,
    UserWord,
    UserActivityData,
    UserArticle,
    UserReadingSession,
    UserExerciseSession,
    StarredArticle,
    ArticleDifficultyFeedback,
    PersonalCopy,
    SearchFilter,
    UserPreference,
    UserCohortMap,
    UserBadgeProgress,
    UserBadge,
    UserAvatar
]


def delete_user_account(db_session, user_to_delete):
    try:
        start_time = time.time()
        total_rows_affected = 0
        articles = Article.uploaded_by(user_to_delete.id)
        print(f"Removing author from Articles:")
        for a in articles:
            a.uploader_id = None
            total_rows_affected += 1
            db_session.add(a)
        print(f"Total of {total_rows_affected} articles altered")
        db_session.commit()

        print(f"Deleting user {user_to_delete.name}...")

        # Delete exercises first (they reference UserWord with NOT NULL constraint)
        user_exercises = (
            Exercise.query.join(UserWord)
            .filter(UserWord.user_id == user_to_delete.id)
            .all()
        )
        print(f"exercise: {len(user_exercises)}")
        for each in user_exercises:
            total_rows_affected += 1
            db_session.delete(each)
        db_session.commit()

        # Clear preferred_bookmark_id on UserWord records to break circular FK
        # (UserWord.preferred_bookmark_id -> Bookmark, Bookmark.user_word_id -> UserWord)
        user_words = UserWord.query.filter_by(user_id=user_to_delete.id).all()
        print(f"Clearing preferred_bookmark_id on {len(user_words)} user_word records")
        for uw in user_words:
            if uw.preferred_bookmark_id is not None:
                uw.preferred_bookmark_id = None
                db_session.add(uw)
        db_session.commit()

        # Delete bookmarks (they reference UserWord with NOT NULL constraint)
        user_bookmarks = Bookmark.find_by_specific_user(user_to_delete)

        # Clean up *_context tables that have NOT NULL bookmark_id
        if user_bookmarks:
            bookmark_ids = [b.id for b in user_bookmarks]
            for ctx_table in bookmark_context_tables:
                ctx_rows = ctx_table.query.filter(
                    ctx_table.bookmark_id.in_(bookmark_ids)
                ).all()
                print(f"{ctx_table.__tablename__}: {len(ctx_rows)}")
                for each in ctx_rows:
                    total_rows_affected += 1
                    db_session.delete(each)
                db_session.commit()

        print(f"bookmark: {len(user_bookmarks)}")
        for each in user_bookmarks:
            total_rows_affected += 1
            db_session.delete(each)
        db_session.commit()

        # Delete user_word_interaction_history (references UserWord)
        user_word_history = (
            UserWordInteractionHistory.query.join(UserWord)
            .filter(UserWord.user_id == user_to_delete.id)
            .all()
        )
        print(f"user_word_interaction_history: {len(user_word_history)}")
        for each in user_word_history:
            total_rows_affected += 1
            db_session.delete(each)
        db_session.commit()

        # Delete friend requests (they can reference a User in two different fields)
        user_friend_requests = FriendRequest.get_all_friend_requests_for_user(user_to_delete.id)
        print(f"friend_request: {len(user_friend_requests)}")
        for each in user_friend_requests:
            total_rows_affected += 1
            db_session.delete(each)
        db_session.commit()

        # Delete friendships (they can reference a User in two different fields)
        user_friends = Friendship.get_friend_objects(user_to_delete.id)
        print(f"friend: {len(user_friends)}")
        for each in user_friends:
            total_rows_affected += 1
            db_session.delete(each)
        db_session.commit()

        # Null out Article.source_upload_id on articles that reference this
        # user's article_upload rows (those articles may belong to other users
        # but were ingested via this user's upload).
        user_uploads = ArticleUpload.query.filter_by(user_id=user_to_delete.id).all()
        if user_uploads:
            upload_ids = [u.id for u in user_uploads]
            referencing_articles = Article.query.filter(
                Article.source_upload_id.in_(upload_ids)
            ).all()
            print(f"articles with source_upload_id pointing at user's uploads: {len(referencing_articles)}")
            for a in referencing_articles:
                a.source_upload_id = None
                db_session.add(a)
            db_session.commit()

        # Delete the user's uploaded example sentences. First drop any
        # ExampleSentenceContext rows referencing them (these can belong to
        # other users' bookmarks; doing so just removes the side-link, the
        # other user's bookmark and exercises survive).
        uploaded_sentences = ExampleSentence.query.filter_by(
            user_id=user_to_delete.id
        ).all()
        if uploaded_sentences:
            sentence_ids = [es.id for es in uploaded_sentences]
            esc_rows = ExampleSentenceContext.query.filter(
                ExampleSentenceContext.example_sentence_id.in_(sentence_ids)
            ).all()
            print(f"example_sentence_context (other users'): {len(esc_rows)}")
            for esc in esc_rows:
                total_rows_affected += 1
                db_session.delete(esc)
            db_session.commit()
        print(f"example_sentence: {len(uploaded_sentences)}")
        for es in uploaded_sentences:
            total_rows_affected += 1
            db_session.delete(es)
        db_session.commit()

        for each_table in tables_to_modify:
            subject_related = each_table.query.filter_by(
                user_id=user_to_delete.id
            ).all()

            print(f"{each_table.__tablename__}: {len(subject_related)}")

            for each in subject_related:
                total_rows_affected += 1
                db_session.delete(each)
            db_session.commit()

        db_session.delete(user_to_delete)
        db_session.commit()
        end_time = time.time() - start_time
        print(
            f"A total of {total_rows_affected} rows were affected. The process took: {end_time:.2f} seconds."
        )
    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
        print(e)
        raise Exception(f"Could not delete the user '{user_to_delete}'")


def delete_user_account_w_session(db_session, user_session_uuid):
    try:
        user_session = Session.find(user_session_uuid)
    except sqlalchemy.exc.IntegrityError:
        raise Exception("Integrity Error")
    except sqlalchemy.exc.NoResultFound:
        raise Exception(f"Couldn't find specified user session: '{user_session_uuid}'")
    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
        print(e)
        raise Exception(
            f"Could not delete the user with session: '{user_session_uuid}'"
        )
    user_to_delete = User.find_by_id(user_session.user_id)
    delete_user_account(db_session, user_to_delete)

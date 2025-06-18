"""
Model Registry

This file imports all model classes to ensure they are registered with SQLAlchemy.
This is necessary so that db.create_all() can create all tables.

DO NOT import from this file - use explicit imports from individual model files instead.
This file exists solely for SQLAlchemy table registration.
"""

# Import all models to register them with SQLAlchemy
from .article_fragment import ArticleFragment
from .article_url_keyword_map import ArticleUrlKeywordMap
from .article_topic_map import ArticleTopicMap
from .user_cohort_map import UserCohortMap
from .language import Language
from .url import Url
from .domain_name import DomainName
from .article import Article
from .text import Text
from .phrase import Phrase
from .bookmark import Bookmark
from .user_preference import UserPreference
from .session import Session
from .unique_code import UniqueCode
from .user import User
from .article_broken_code_map import ArticleBrokenMap
from .article_fragment_context import ArticleFragmentContext
from .article_title_context import ArticleTitleContext
from .meaning import Meaning
from .cohort import Cohort
from .user_language import UserLanguage
from .user_article import UserArticle
from .article_difficulty_feedback import ArticleDifficultyFeedback
from .feed import Feed
from .url_keyword import UrlKeyword
from .search import Search
from .search_filter import SearchFilter
from .search_subscription import SearchSubscription
from .exercise import Exercise
from .exercise_outcome import ExerciseOutcome
from .exercise_source import ExerciseSource
from .user_activitiy_data import UserActivityData
from .teacher_cohort_map import TeacherCohortMap
from .teacher import Teacher
from .cohort_article_map import CohortArticleMap
from .topic import Topic
from .topic_subscription import TopicSubscription
from .topic_filter import TopicFilter
from .user_reading_session import UserReadingSession
from .user_exercise_session import UserExerciseSession
from .personal_copy import PersonalCopy
from .difficulty_lingo_rank import DifficultyLingoRank
from .yt_channel import YTChannel
from .video import Video
from .caption import Caption
from .video_tag import VideoTag
from .video_tag_map import VideoTagMap
from .video_caption_context import VideoCaptionContext
from .video_title_context import VideoTitleContext
from .video_topic_map import VideoTopicMap
from .user_video import UserVideo
from .user_watching_session import UserWatchingSession
from .starred_article import StarredArticle
from .source_type import SourceType
from .source_text import SourceText
from .source import Source
from .notification import Notification
from .new_text import NewText
from .feedback_component import FeedbackComponent
from .context_type import ContextType
from .bookmark_context import BookmarkContext
from .bookmark_user_preference import UserWordExPreference
from .article_topic_user_feedback import ArticleTopicUserFeedback
from .user_notification import UserNotification
from .user_feedback import UserFeedback

# Import the scheduling model
from ..word_scheduling.basicSR.basicSR import BasicSRSchedule
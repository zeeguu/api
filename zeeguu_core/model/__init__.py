import re
import flask_sqlalchemy

import zeeguu_core
from flask import Flask

from zeeguu_core.configuration.configuration import load_configuration_or_abort

# If zeeguu_core.app is already defined we use that object
# as the app for the db_init that we do later. If not,
# we create the app here and load the corresponding configuration
if not hasattr(zeeguu_core, "app"):
    zeeguu_core.app = Flask("Zeeguu-Core")
    load_configuration_or_abort(
        zeeguu_core.app,
        "ZEEGUU_CONFIG",
        ["MAX_SESSION", "SQLALCHEMY_DATABASE_URI", "SQLALCHEMY_TRACK_MODIFICATIONS"],
    )

# Create the zeeguu_core.db object, which will be the superclass
# of all the model classes
zeeguu_core.db = flask_sqlalchemy.SQLAlchemy(zeeguu_core.app)
# Note, that if we pass the app here, then we don't need later
# to push the app context

# the core model
from .language import Language
from .url import Url
from .domain_name import DomainName
from .article import Article
from .bookmark import Bookmark
from .text import Text
from .user import User
from .user_word import UserWord
from .user_preference import UserPreference
from .session import Session
from .unique_code import UniqueCode
from .word_knowledge.word_interaction_history import WordInteractionHistory

from .user_language import UserLanguage

from .topic import Topic
from .user_article import UserArticle
from .article_word import ArticleWord
from .articles_cache import ArticlesCache

from .feed import RSSFeed
from .feed_registrations import RSSFeedRegistration

from .topic import Topic
from .topic_subscription import TopicSubscription
from .topic_filter import TopicFilter
from .localized_topic import LocalizedTopic

from .search import Search
from .search_filter import SearchFilter
from .search_subscription import SearchSubscription

# exercises
from .exercise import Exercise
from .exercise_outcome import ExerciseOutcome
from .exercise_source import ExerciseSource

# user logging
from .user_activitiy_data import UserActivityData
from .smartwatch.watch_event_type import WatchEventType
from .smartwatch.watch_interaction_event import WatchInteractionEvent

# teachers and cohorts
from .cohort import Cohort
from .teacher_cohort_map import TeacherCohortMap
from .teacher import Teacher
from .cohort_article_map import CohortArticleMap

from .user_reading_session import UserReadingSession
from .user_exercise_session import UserExerciseSession

# bookmark scheduling
from zeeguu_core.model.bookmark_priority_arts import BookmarkPriorityARTS

# Creating the DB tables if needed
# Note that this must be called after all the model classes are loaded
zeeguu_core.db.init_app(zeeguu_core.app)
zeeguu_core.db.create_all(app=zeeguu_core.app)

# Log the DB connection string; after masking the password
db_connection_string = zeeguu_core.app.config["SQLALCHEMY_DATABASE_URI"]
anon_conn_string = re.sub(":([a-zA-Z_][a-zA-Z_0-9]*)@", ":****@", db_connection_string)
zeeguu_core.warning("*** ==== ZEEGUU CORE: Linked model with: " + anon_conn_string)


# install nltk punkt & tagger if missing
# we can only do it here because the nltk loads in memory the unittest
# and when that is detected, the configuration of the system is set to
# testing... and it does not configure the model with the right db
import nltk

try:
    nltk.sent_tokenize("I am a berliner.")
except LookupError as e:
    nltk.download("punkt")
    nltk.download("averaged_perceptron_tagger")

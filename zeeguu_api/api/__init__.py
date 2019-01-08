import flask
import zeeguu_core

api = flask.Blueprint("api", __name__)
db_session = zeeguu_core.db.session


# These files have to be imported after this line;
# They enrich the api object
from . import exercises
from . import feeds
from . import sessions
from . import smartwatch
from . import system_languages
from . import translate_and_bookmark
from . import user_activity
from . import bookmarks_and_words
from . import user
from . import user_statistics
from . import recommendations
from . import user_article
from . import user_articles
from . import user_languages
from . import teacher_dashboard
from . import topics
from . import search
from . import article
from . import accounts
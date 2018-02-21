import flask
api = flask.Blueprint("api", __name__)
# These files have to be imported after this line;
# They enrich the api object
from . import exercises
from . import feeds
from . import sessions
from . import smartwatch
from . import system_languages
from . import translate_and_bookmark
from . import upload_user_activity_data
from . import user_data
from . import user_settings
from . import user_statistics
from . import starred_articles
from . import recommendations
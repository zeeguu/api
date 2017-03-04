import flask
api = flask.Blueprint("api", __name__)
# These files have to be imported after this line;
# They enrich the api object
import download_content_from_url
import exercises
import feeds
import sessions
import smartwatch
import system_languages
import text_analysis
import translate_and_bookmark
import upload_user_activity_data
import user_data
import user_settings
import user_statistics
import flask
api = flask.Blueprint("api", __name__)
# These files have to be imported after this line;
# They enrich the api object
from . import download_content_from_url
from . import exercises
from . import feeds
from . import sessions
from . import smartwatch
from . import system_languages
from . import text_analysis
from . import translate_and_bookmark
from . import upload_user_activity_data
from . import user_data
from . import user_settings
from . import user_statistics
from . import starred_articles

# The code below is for the Flask Dashboard plugin.
# This code will enable the grouping of unit test results 
# by the endpoint that they test.
from flask import request
import datetime
import os
log_dir = os.getenv('DASHBOARD_LOG_DIR')
@api.after_request
def after_request(response):
    t1 = str(datetime.datetime.now())
    log = open(log_dir + "endpoint_hits.log", "a")
    log.write("\"{}\",\"{}\"\n".format(t1, request.endpoint))
    log.close()
    return response

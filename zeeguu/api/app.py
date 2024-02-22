# -*- coding: utf8 -*-
from zeeguu.config.loader import load_configuration_or_abort
from flask_cors import CORS
from flask import Flask
import time
import os
import re
import zeeguu

from zeeguu.logging import warning

# apimux is quite noisy; supress it's output
import logging
from apimux.log import logger

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

if os.environ.get("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.environ.get("SENTRY_DSN"),
        integrations=[FlaskIntegration()],
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production.
        traces_sample_rate=0.3,
    )

logger.setLevel(logging.CRITICAL)


def create_app(testing=False):
    # *** Creating and starting the App *** #
    app = Flask("Zeeguu-API")
    CORS(app)

    if testing:
        app.testing = True

    load_configuration_or_abort(
        app,
        "ZEEGUU_CONFIG",
        [  # first three are required by core
            "MAX_SESSION",
            "SQLALCHEMY_DATABASE_URI",
            "SQLALCHEMY_TRACK_MODIFICATIONS",
            # next three are required by API when
            # run locally
            "DEBUG",
            "HOST",
            "SECRET_KEY",
            # the following are required by the API
            # for user account creation & password recovery
            "INVITATION_CODES",
            "SMTP_EMAIL",
        ],
    )

    # if we don't specify the charset in the connection string
    # we are not able to store emojis
    app.config["SQLALCHEMY_DATABASE_URI"] += "?charset=utf8mb4"
    # inspired from: https://stackoverflow.com/a/47278172/1200070

    from zeeguu.core.model import db

    db.init_app(app)

    # Creating the DB tables if needed
    # Note that this must be called after all the model classes are loaded
    # And they are loaded above, in the import db... which implicitly loads the model package
    with app.app_context():
        db.create_all()

    from .endpoints import api

    app.register_blueprint(api)

    # We're saving the zeeguu.core.app so we can refer to the config from deep in the code...
    zeeguu.core.app = app

    print(app.config)
    # Log the DB connection string; after masking the password
    db_connection_string = app.config["SQLALCHEMY_DATABASE_URI"]
    anon_conn_string = re.sub(
        ":([a-zA-Z_][a-zA-Z_0-9]*)@", ":****@", db_connection_string
    )
    warning("*** ==== ZEEGUU CORE: Linked model with: " + anon_conn_string)

    return app


# # The zeeguu.core.model  module relies on an app being injected from outside
# # ----------------------------------------------------------------------
# import zeeguu.core
#
# zeeguu.core.app = app
# import zeeguu.core.model


# -----------------


# try:
#     import flask_monitoringdashboard as dashboard
#     from .custom_fmd_graphs import daily_visitors

#     dashboard.config.init_from(envvar="FLASK_MONITORING_DASHBOARD_CONFIG")

#     from zeeguu.core.model import Session

#     dashboard.config.get_group_by = lambda: Session.find(request=flask.request).user_id
#     dashboard.bind(app=app)
#     daily_visitors(dashboard)
#     print("Started the Flask Monitoring Dashboard")

# except Exception as e:
#     import traceback

#     traceback.print_exc()
#     print("flask_monitornig_dashboard package is not present. Running w/o FMD.")


# install nltk punkt & tagger if missing
# we can only do it here because the nltk loads in memory the unittest
# and when that is detected, the configuration of the system is set to
# testing... and it does not configure the model with the right db
import nltk

try:
    nltk.data.path.append("/var/www/nltk_data")
    nltk.sent_tokenize("I am a berliner.")
except LookupError as e:
    nltk.download("punkt")
    nltk.download("averaged_perceptron_tagger")

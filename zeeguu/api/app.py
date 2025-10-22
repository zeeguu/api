# -*- coding: utf8 -*-
from zeeguu.config.loader import load_configuration_or_abort
from flask_cors import CORS
from flask import Flask, send_from_directory
import time
import os
import re
import zeeguu
from zeeguu.config import ZEEGUU_DATA_FOLDER

from zeeguu.logging import warning

# apimux is quite noisy; supress it's output
import logging
from apimux.log import logger

# Suppress verbose Elasticsearch connection error logs
logging.getLogger("elastic_transport.transport").setLevel(logging.ERROR)
logging.getLogger("elastic_transport.node_pool").setLevel(logging.ERROR)

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

    from zeeguu.core.model.db import db

    db.init_app(app)

    # Creating the DB tables if needed
    # Note that this must be called after all the model classes are loaded
    # And they are loaded above, in the import db... which implicitly loads the model package
    with app.app_context():
        db.create_all()

    from .endpoints import api

    app.register_blueprint(api)

    # Add static file serving for audio files
    @app.route("/audio/<path:filename>")
    def serve_audio(filename):
        """Serve audio files from the ZEEGUU_DATA_FOLDER/audio directory"""
        audio_dir = os.path.join(ZEEGUU_DATA_FOLDER, "audio")
        return send_from_directory(audio_dir, filename)

    # We're saving the zeeguu.core.app so we can refer to the config from deep in the code...
    zeeguu.core.app = app

    # print(app.config)
    # Log the DB connection string; after masking the password
    db_connection_string = app.config["SQLALCHEMY_DATABASE_URI"]
    anon_conn_string = re.sub(
        ":([a-zA-Z_][a-zA-Z_0-9\-]*)@", ":****@", db_connection_string
    )
    warning("*** ==== ZEEGUU CORE: Linked model with: " + anon_conn_string)

    # Preload wordstats in production for faster response times
    if app.config.get("PRELOAD_WORDSTATS", False):
        warning("*** Preloading wordstats dictionaries...")
        start_time = time.time()
        from wordstats import LanguageInfo

        # Get all supported languages from the database
        from zeeguu.core.model import Language
        with app.app_context():
            all_languages = Language.all_languages()
            language_codes = [lang.code for lang in all_languages]

        # Preload all language dictionaries
        LanguageInfo.load_in_memory_for(language_codes)

        elapsed = time.time() - start_time
        warning(f"*** Wordstats preloaded {len(language_codes)} languages in {elapsed:.2f}s")
    else:
        warning("*** Wordstats will use lazy loading (PRELOAD_WORDSTATS=False)")

    return app

# -*- coding: utf8 -*-
from zeeguu.config.loader import load_configuration_or_abort
from flask_cors import CORS
from flask import Flask, send_from_directory
import flask
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

    # Configure connection pool to handle concurrent requests
    # Default is 5 + 10 overflow = 15 total connections
    # Increase to handle higher concurrency
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_size": 10,  # Core pool size (up from default 5)
        "max_overflow": 20,  # Additional connections when pool exhausted (up from default 10)
        "pool_recycle": 3600,  # Recycle connections after 1 hour to avoid MySQL timeout
        "pool_pre_ping": True,  # Verify connections before using them
    }

    from zeeguu.core.model.db import db

    db.init_app(app)

    # Add SQL query listener to catch source_text queries
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    import sys

    @event.listens_for(Engine, "before_cursor_execute")
    def detect_source_text_query(conn, cursor, statement, parameters, context, executemany):
        if "source_text" in statement.lower():
            # Check if it's a full table scan (SELECT without WHERE on source_text)
            if "select" in statement.lower() and "from source_text" in statement.lower():
                if "where" not in statement.lower():
                    print(f"\n!!! FULL TABLE SCAN DETECTED ON source_text !!!", file=sys.stderr)
                    print(f"Statement: {statement[:500]}", file=sys.stderr)
                    print(f"Parameters: {parameters}", file=sys.stderr)
                    import traceback
                    print("Call stack:", file=sys.stderr)
                    traceback.print_stack(file=sys.stderr)
                    sys.stderr.flush()

    # Creating the DB tables if needed
    # Note that this must be called after all the model classes are loaded
    # And they are loaded above, in the import db... which implicitly loads the model package
    with app.app_context():
        db.create_all()

    from .endpoints import api

    app.register_blueprint(api)

    # Add request logging to catch ALL requests before they hit endpoints
    @app.before_request
    def log_request_start():
        import sys
        import time
        import threading
        thread_id = threading.current_thread().ident
        timestamp = time.time()
        print(f"[FLASK-REQUEST-START] {flask.request.method} {flask.request.path} [thread={thread_id}] [time={timestamp}]", file=sys.stderr)
        sys.stderr.flush()

    # Clean up database session after each request to return connections to pool
    # Using both teardown_request and teardown_appcontext to ensure it runs
    @app.teardown_request
    def shutdown_session_request(exception=None):
        import sys
        import threading
        import time
        thread_id = threading.current_thread().ident
        timestamp = time.time()
        print(f"[DB-SESSION-TEARDOWN-REQUEST] Removing session [thread={thread_id}] [time={timestamp}]", file=sys.stderr)
        sys.stderr.flush()
        db.session.remove()
        print(f"[DB-SESSION-TEARDOWN-REQUEST] Session removed successfully [thread={thread_id}]", file=sys.stderr)
        sys.stderr.flush()
        if exception:
            print(f"[DB-SESSION-TEARDOWN-REQUEST] Exception during request: {exception}", file=sys.stderr)
            sys.stderr.flush()

    @app.teardown_appcontext
    def shutdown_session_appcontext(exception=None):
        import sys
        import threading
        import time
        thread_id = threading.current_thread().ident
        timestamp = time.time()
        print(f"[DB-SESSION-TEARDOWN-APPCONTEXT] Removing session [thread={thread_id}] [time={timestamp}]", file=sys.stderr)
        sys.stderr.flush()
        db.session.remove()
        print(f"[DB-SESSION-TEARDOWN-APPCONTEXT] Session removed successfully [thread={thread_id}]", file=sys.stderr)
        sys.stderr.flush()
        if exception:
            print(f"[DB-SESSION-TEARDOWN-APPCONTEXT] Exception during request: {exception}", file=sys.stderr)
            sys.stderr.flush()

    # Add static file serving for audio files
    @app.route("/audio/<path:filename>")
    def serve_audio(filename):
        """Serve audio files from the ZEEGUU_DATA_FOLDER/audio directory"""
        audio_dir = os.path.join(ZEEGUU_DATA_FOLDER, "audio")
        return send_from_directory(audio_dir, filename)

    # We're saving the zeeguu.core.app so we can refer to the config from deep in the code...
    zeeguu.core.app = app

    # print(app.config)
    # Log the current git commit hash
    try:
        import subprocess
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=os.path.dirname(__file__),
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()[:8]
        git_branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=os.path.dirname(__file__),
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
        warning(f"*** ==== ZEEGUU API VERSION: {git_branch}@{git_hash}")
    except Exception:
        warning("*** ==== ZEEGUU API VERSION: <git info unavailable>")

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

        # Use CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED for preloading
        # (these are the languages that have wordstats data)
        language_codes = Language.CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED

        # Preload all language dictionaries
        LanguageInfo.load_in_memory_for(language_codes)

        elapsed = time.time() - start_time
        warning(f"*** Wordstats preloaded {len(language_codes)} languages in {elapsed:.2f}s")
    else:
        warning("*** Wordstats will use lazy loading (PRELOAD_WORDSTATS=False)")

    # Preload Stanza tokenizers to avoid blocking during requests
    # This must run inside app context since it needs the database
    with app.app_context():
        if app.config.get("PRELOAD_STANZA", True):  # Default to True
            warning("*** Preloading Stanza tokenizers...")
            start_time = time.time()
            from zeeguu.core.model import Language
            from zeeguu.core.tokenization import get_tokenizer, TOKENIZER_MODEL

            language_codes = Language.CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED

            # Preload tokenizers for all supported languages
            # Use get_tokenizer() to ensure we create the exact same tokenizer as during requests
            for lang_code in language_codes:
                try:
                    language = Language.find_or_create(lang_code)
                    # Create tokenizer using the same function as requests (will cache the model)
                    tokenizer = get_tokenizer(language, TOKENIZER_MODEL)
                    # Tokenize a dummy word to ensure model is fully loaded
                    tokenizer.tokenize_text("test")
                    warning(f"*** Preloaded Stanza tokenizer for {lang_code}")
                except Exception as e:
                    warning(f"*** Failed to preload Stanza for {lang_code}: {e}")

            elapsed = time.time() - start_time
            warning(f"*** Stanza tokenizers preloaded for {len(language_codes)} languages in {elapsed:.2f}s")
        else:
            warning("*** Stanza tokenizers will use lazy loading (PRELOAD_STANZA=False)")

    return app

"""
Minimal Flask app for testing core models.

This avoids core depending on api for test infrastructure.
"""
from flask import Flask

import zeeguu


def create_test_app():
    """
    Create a minimal Flask app for testing core models.

    This is a lightweight app that only sets up:
    - SQLAlchemy with an in-memory SQLite database
    - Basic configuration

    It does NOT include API endpoints, monitoring, or any other api-specific setup.
    """
    app = Flask("Zeeguu-Core-Test")
    app.testing = True

    # Use in-memory SQLite for fast tests
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_SESSION"] = 99999999
    app.config["DEBUG"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["INVITATION_CODES"] = "test-code"
    app.config["SMTP_EMAIL"] = "test@test.com"

    from zeeguu.core.model.db import db

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Set zeeguu.core.app for code that needs config access
    zeeguu.core.app = app

    return app

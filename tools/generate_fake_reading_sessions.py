#!/usr/bin/env python
import sys
import os
import random
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# REQUIRED: Initialize Flask app context for database access
from zeeguu.api.app import create_app
from zeeguu.core.model import db
app = create_app()
app.app_context().push()

from zeeguu.core.model.user import User
from zeeguu.core.model.article import Article
from zeeguu.core.model.user_reading_session import UserReadingSession

def get_random_user():
    users = User.query.all()
    return random.choice(users) if users else None

def get_random_article():
    articles = Article.query.all()
    return random.choice(articles) if articles else None

def random_datetime_in_last_month():
    now = datetime.now()
    start = now - timedelta(days=30)
    return start + timedelta(seconds=random.randint(0, int((now - start).total_seconds())))

READING_SOURCES = ['extension', 'web']
PLATFORMS = [1, 2, 3]  # Example platform codes; adjust as needed

def main():
    num_sessions = 50
    created = 0
    for _ in range(num_sessions):
      #   user = get_random_user()
        user = User.find_by_id(5) 
        article = get_random_article()
        if not user or not article:
            print("Not enough users or articles in the DB.")
            break
        start_time = random_datetime_in_last_month()
        duration = random.randint(1, 30) * 60 * 1000  # 1-30 minutes in ms
        last_action_time = start_time + timedelta(milliseconds=duration)
        reading_source = random.choice(READING_SOURCES)
        platform = random.choice(PLATFORMS)
        session = UserReadingSession(
            user_id=user.id,
            article_id=article.id,
            current_time=start_time,
            reading_source=reading_source,
            platform=platform
        )
        session.duration = duration
        session.last_action_time = last_action_time
        session.is_active = False
        db.session.add(session)
        created += 1
    db.session.commit()
    print(f"Created {created} UserReadingSession records.")

if __name__ == "__main__":
    main()

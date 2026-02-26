#!/usr/bin/env python
import os
os.environ["PRELOAD_STANZA"] = "false"

"""

   Script that goes through all the users in a DB
   and replaces their names and emails with random ones.
   Also deletes unreferenced articles.

"""

import sqlalchemy

import zeeguu.core
from faker import Faker
from zeeguu.api.app import create_app
from zeeguu.core.model import User, Article
from zeeguu.core.model.user_article import UserArticle
from zeeguu.core.model.text import Text
from zeeguu.core.model.user_activitiy_data import UserActivityData

app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session

# Delete unreferenced articles
from sqlalchemy import text

print("Building set of referenced article IDs...")

# Get referenced article IDs from each table separately (fast indexed queries)
print("  - checking user_article...")
ref1 = set(row[0] for row in db_session.execute(text("SELECT DISTINCT article_id FROM user_article WHERE article_id IS NOT NULL")))
print(f"    {len(ref1)} articles")

print("  - checking text...")
ref2 = set(row[0] for row in db_session.execute(text("SELECT DISTINCT article_id FROM text WHERE article_id IS NOT NULL")))
print(f"    {len(ref2)} articles")

print("  - checking user_reading_session...")
ref3 = set(row[0] for row in db_session.execute(text("SELECT DISTINCT article_id FROM user_reading_session WHERE article_id IS NOT NULL")))
print(f"    {len(ref3)} articles")

print("  - checking user_activity_data source_ids...")
source_ids = set(row[0] for row in db_session.execute(text("SELECT DISTINCT source_id FROM user_activity_data WHERE source_id IS NOT NULL")))
print(f"    {len(source_ids)} source_ids")

referenced_article_ids = ref1 | ref2 | ref3
print(f"Total referenced articles: {len(referenced_article_ids)}")

# Get all article IDs and their source_ids
print("Getting all article IDs...")
all_articles = list(db_session.execute(text("SELECT id, source_id FROM article")))
print(f"Total articles: {len(all_articles)}")

# Find unreferenced
unreferenced_ids = [
    row[0] for row in all_articles
    if row[0] not in referenced_article_ids and row[1] not in source_ids
]
total = len(unreferenced_ids)
print(f"Found {total} unreferenced articles to delete")

# Delete in batches with progress
# Disable FK checks for faster deletes (we already verified no references exist)
db_session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
db_session.commit()

batch_size = 100
deleted = 0
for i in range(0, total, batch_size):
    batch = unreferenced_ids[i:i + batch_size]
    if batch:
        placeholders = ",".join(str(id) for id in batch)
        try:
            db_session.execute(text(f"DELETE FROM article WHERE id IN ({placeholders})"))
            db_session.commit()
        except Exception as e:
            print(f"Error deleting batch, rolling back: {e}")
            db_session.rollback()
            continue
        deleted += len(batch)
        if deleted % 10000 == 0 or deleted == total:
            print(f"Deleted {deleted}/{total} articles ({100*deleted//total}%)")

db_session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
db_session.commit()
print(f"Done deleting {deleted} unreferenced articles")

# Anonymize users
fake = Faker()

# Pre-compute one bcrypt hash and reuse for all users (much faster)
from werkzeug.security import generate_password_hash
ANON_PASSWORD_HASH = generate_password_hash("supersecret")

print("Anonymizing users...")
for user in User.query.all():
    for _ in range(0, 13):
        try:
            user.name = fake.name()
            user.email = fake.email()
            user.password = ANON_PASSWORD_HASH  # Use pre-computed hash
            db_session.add(user)
            db_session.commit()
            print(f"anonymized user id {user.id} to {user.name}")
            break
        except sqlalchemy.exc.IntegrityError as e:
            db_session.rollback()
            print(f"retrying...")
            continue

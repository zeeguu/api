#!/usr/bin/env python
import os
os.environ["PRELOAD_STANZA"] = "false"

"""
   Goes through all users in a DB and replaces their names and emails with
   random ones. Also deletes unreferenced articles.

   Article deletion uses the shared zeeguu.core.article_pruning helpers, so it
   deletes cleanly (FK checks ON, DB cascades owned children, shared content
   reclaimed inline) and never leaves orphans behind — same code path as
   tools/prune_old_articles.py. Requires migration
   26-05-26--restrict-article-fk-for-prune-protection.sql.
"""

import sqlalchemy

import zeeguu.core
from faker import Faker
from sqlalchemy import text
from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import User
from zeeguu.core.article_pruning import (
    referenced_article_ids,
    delete_articles_in_batches,
)

app = create_app_for_scripts()
app.app_context().push()

db_session = zeeguu.core.model.db.session

# ---- Delete unreferenced articles (cleanly: FK-on, cascade, inline reclaim) ----
referenced = referenced_article_ids(db_session)

all_ids = [r[0] for r in db_session.execute(text("SELECT id FROM article"))]
unreferenced = [aid for aid in all_ids if aid not in referenced]
print(
    f"\nDeleting {len(unreferenced)} unreferenced articles "
    f"(keeping {len(referenced)} referenced of {len(all_ids)} total)..."
)
if unreferenced:
    delete_articles_in_batches(db_session, unreferenced)

# ---- Anonymize users ----
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
        except sqlalchemy.exc.IntegrityError:
            db_session.rollback()
            print("retrying...")
            continue

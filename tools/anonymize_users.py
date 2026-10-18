#!/usr/bin/env python
"""
   Goes through all users in a DB and replaces their names and emails with
   random ones. Also deletes unreferenced articles, and scrubs the other
   personal free text the pipeline used to leave in place:

   - unique_code.email (verification codes keyed by email)
   - cohort.name / cohort.inv_code (school and class names)
   - user_feedback.message
   - user-uploaded articles (article.uploader_id set, plus their simplified
     children): title, content, summary, authors, the level-adapted texts,
     the tokenization cache, their fragment texts and source text (only rows
     no other article shares), and the article_upload rows
   - user_activity_data.extra_data, and .value for search events
   - search terms: search.keywords, translation_search.search_word

   Run only against the anonymization copy (ZEEGUU_CONFIG=anon_api.cfg).
   Still not covered: bookmark contexts taken from uploaded texts, user ids
   (the result is pseudonymous), see docs/security/SECURITY_ASSESSMENT_2026-10.md M1.

   Article deletion uses the shared zeeguu.core.article_pruning helpers, so it
   deletes cleanly (FK checks ON, DB cascades owned children, shared content
   reclaimed inline) and never leaves orphans behind — same code path as
   tools/prune_old_articles.py. Requires migration
   26-05-26--restrict-article-fk-for-prune-protection.sql.
"""

import sqlalchemy

import zeeguu.core
from faker import Faker
from sqlalchemy import bindparam, text
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


# ---- Scrub other personal free text ----
def _stmt(sql, params):
    stmt = text(sql)
    if params and "ids" in params:
        # `IN :ids` takes a list, expanded into one placeholder per id.
        stmt = stmt.bindparams(bindparam("ids", expanding=True))
    return stmt


def run(label, sql, params=None):
    result = db_session.execute(_stmt(sql, params), params or {})
    db_session.commit()
    print(f"  {label}: {result.rowcount} rows")


def ids(sql, params=None):
    return [r[0] for r in db_session.execute(_stmt(sql, params), params or {})]


def in_batches(id_list, size=1000):
    for i in range(0, len(id_list), size):
        yield id_list[i : i + size]


print("Scrubbing personal free text...")

run(
    "unique_code.email",
    "UPDATE unique_code SET email = CONCAT('code', id, '@example.invalid')",
)
run(
    "cohort.name / inv_code",
    "UPDATE cohort SET name = CONCAT('Class ', id), inv_code = CONCAT('inv', id)",
)
run("user_feedback.message", "UPDATE user_feedback SET message = ''")
run(
    "user_activity_data.extra_data",
    "UPDATE user_activity_data SET extra_data = '' WHERE extra_data IS NOT NULL AND extra_data <> ''",
)
# The web app logs the query itself as the value of its search events
# (SEARCH QUERY, SUBSCRIBE_TO_SEARCH, UNSUBSCRIBE_FROM_SEARCH).
run(
    "user_activity_data.value of search events",
    "UPDATE user_activity_data SET value = '' "
    "WHERE event LIKE '%SEARCH%' AND value IS NOT NULL AND value <> ''",
)
run("search.keywords", "UPDATE search SET keywords = CONCAT('search', id)")
run(
    "translation_search.search_word",
    "UPDATE translation_search SET search_word = CONCAT('word', id)",
)

# User-uploaded articles and everything derived from them. Ids are collected
# first: MySQL can't UPDATE article with a subquery that reads article (1093).
uploaded = set(ids("SELECT id FROM article WHERE uploader_id IS NOT NULL"))
frontier = set(uploaded)
while frontier:
    children = set()
    for batch in in_batches(sorted(frontier)):
        children.update(
            ids(
                "SELECT id FROM article WHERE parent_article_id IN :ids",
                {"ids": list(batch)},
            )
        )
    frontier = children - uploaded
    uploaded |= frontier
uploaded = sorted(uploaded)
print(f"  {len(uploaded)} uploaded articles (including simplified versions)")

# Text rows are deduplicated by content hash, so a paragraph can be shared with
# a crawled article. Only scrub rows that no other article uses.
fragment_texts, source_texts = set(), set()
for batch in in_batches(uploaded):
    params = {"ids": list(batch)}
    fragment_texts.update(
        ids(
            "SELECT DISTINCT f.text_id FROM article_fragment f "
            "WHERE f.article_id IN :ids AND f.text_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM article_fragment o "
            "  WHERE o.text_id = f.text_id AND o.article_id NOT IN :ids)",
            params,
        )
    )
    source_texts.update(
        ids(
            "SELECT DISTINCT s.source_text_id FROM article a "
            "JOIN source s ON s.id = a.source_id "
            "WHERE a.id IN :ids AND s.source_text_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM article a2 JOIN source s2 ON s2.id = a2.source_id "
            "  WHERE s2.source_text_id = s.source_text_id AND a2.id NOT IN :ids)",
            params,
        )
    )
# "Other" is checked per batch, so a text shared by two uploaded articles in
# different batches counts as shared and is kept. That errs towards keeping
# text, and with fewer than 1000 uploads there is only one batch.

for batch in in_batches(uploaded):
    params = {"ids": list(batch)}
    run(
        "article (uploaded)",
        "UPDATE article SET title = CONCAT('Uploaded text ', id), content = '', "
        "htmlContent = NULL, summary = NULL, authors = '' WHERE id IN :ids",
        params,
    )
    run(
        "level_adapted_article_text (uploaded)",
        "UPDATE level_adapted_article_text SET title = NULL, tokenized_title = NULL, "
        "summary = NULL, tokenized_summary = NULL WHERE article_id IN :ids",
        params,
    )
    run(
        "article_tokenization_cache (uploaded)",
        "DELETE FROM article_tokenization_cache WHERE article_id IN :ids",
        params,
    )
for batch in in_batches(sorted(fragment_texts)):
    run(
        "new_text of uploaded fragments",
        "UPDATE new_text SET content = '', "
        "content_hash = SHA2(CONCAT('scrubbed-new_text-', id), 256) WHERE id IN :ids",
        {"ids": list(batch)},
    )
for batch in in_batches(sorted(source_texts)):
    run(
        "source_text of uploaded articles",
        "UPDATE source_text SET content = '', "
        "content_hash = SHA2(CONCAT('scrubbed-source_text-', id), 256) WHERE id IN :ids",
        {"ids": list(batch)},
    )
run(
    "article_upload",
    "UPDATE article_upload SET title = CONCAT('Uploaded text ', id), raw_html = NULL, "
    "text_content = NULL, author = NULL, image_url = NULL",
)
print("Done.")

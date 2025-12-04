#!/usr/bin/env python
"""
One-time script to decode HTML entities in article titles and summaries.

Fixes &quot; &amp; &lt; &gt; etc. appearing in text.

Run: python tools/one_time/fix_html_entities_in_articles.py
"""
import sys
import os
import html

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model import Article

# Common HTML entities to check for
ENTITY_PATTERNS = ['&quot;', '&amp;', '&lt;', '&gt;', '&apos;', '&#']

def has_html_entities(text):
    if not text:
        return False
    return any(pattern in text for pattern in ENTITY_PATTERNS)

# Find articles with HTML entities in title or summary
print("Searching for articles with HTML entities...")

articles = Article.query.all()
total = len(articles)
fixed_titles = 0
fixed_summaries = 0

for i, article in enumerate(articles, 1):
    changed = False

    if has_html_entities(article.title):
        article.title = html.unescape(article.title)
        fixed_titles += 1
        changed = True

    if has_html_entities(article.summary):
        article.summary = html.unescape(article.summary)
        fixed_summaries += 1
        changed = True

    if changed:
        db.session.add(article)

    if i % 10000 == 0:
        db.session.commit()
        print(f"  {i}/{total} checked... (fixed {fixed_titles} titles, {fixed_summaries} summaries)")

db.session.commit()
print(f"Done! Fixed {fixed_titles} titles and {fixed_summaries} summaries.")

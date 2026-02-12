#!/usr/bin/env python
"""
Clean up example sentences generated today (only unreferenced ones).
Run with: source ~/.venvs/z_env/bin/activate && python tools/cleanup_todays_examples.py
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model.example_sentence import ExampleSentence
from zeeguu.core.model.example_sentence_context import ExampleSentenceContext

# Find examples created today
today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

examples_today = ExampleSentence.query.filter(
    ExampleSentence.created_at >= today_start
).all()

print(f"Found {len(examples_today)} examples created today")

# Check which ones are referenced by bookmarks
referenced_ids = set(
    ctx.example_sentence_id for ctx in
    ExampleSentenceContext.query.filter(
        ExampleSentenceContext.example_sentence_id.in_([e.id for e in examples_today])
    ).all()
) if examples_today else set()

unreferenced = [ex for ex in examples_today if ex.id not in referenced_ids]
referenced = [ex for ex in examples_today if ex.id in referenced_ids]

print(f"  - {len(unreferenced)} unreferenced (safe to delete)")
print(f"  - {len(referenced)} referenced by bookmarks (will keep)")

if unreferenced:
    print("\nUnreferenced examples:")
    for ex in unreferenced[:5]:
        print(f"  - {ex.sentence[:60]}...")
    if len(unreferenced) > 5:
        print(f"  ... and {len(unreferenced) - 5} more")

    confirm = input(f"\nDelete {len(unreferenced)} unreferenced examples? (yes/no): ")
    if confirm.lower() == "yes":
        for ex in unreferenced:
            db.session.delete(ex)
        db.session.commit()
        print(f"Deleted {len(unreferenced)} examples")
    else:
        print("Cancelled")
else:
    print("\nNo unreferenced examples to delete")

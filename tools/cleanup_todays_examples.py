#!/usr/bin/env python
"""
Clean up example sentences generated today.
Run with: source ~/.venvs/z_env/bin/activate && python tools/cleanup_todays_examples.py
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model.example_sentence import ExampleSentence

# Find examples created today
today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

examples_today = ExampleSentence.query.filter(
    ExampleSentence.time >= today_start
).all()

print(f"Found {len(examples_today)} examples created today")

if examples_today:
    for ex in examples_today[:5]:  # Show first 5
        print(f"  - {ex.sentence[:60]}...")
    
    confirm = input("\nDelete all? (yes/no): ")
    if confirm.lower() == "yes":
        for ex in examples_today:
            db.session.delete(ex)
        db.session.commit()
        print(f"Deleted {len(examples_today)} examples")
    else:
        print("Cancelled")
else:
    print("Nothing to delete")

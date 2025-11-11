#!/usr/bin/env python
"""
Test script to verify the integrity validation is working correctly.
This should raise an exception when we try to set an invalid preferred_bookmark_id.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# REQUIRED: Initialize Flask app context for database access
from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model import UserWord, Bookmark

# Find a UserWord with at least one bookmark
user_word = UserWord.query.filter(UserWord.preferred_bookmark_id != None).first()

if not user_word:
    print("No UserWords found to test with")
    sys.exit(1)

print(f"Testing with UserWord {user_word.id}: '{user_word.meaning.origin.content}'")
print(f"Current preferred_bookmark_id: {user_word.preferred_bookmark_id}")

# Find a bookmark that belongs to a DIFFERENT UserWord
different_bookmark = (
    Bookmark.query.filter(Bookmark.user_word_id != user_word.id)
    .first()
)

if not different_bookmark:
    print("No different bookmarks found to test with")
    sys.exit(1)

print(f"\nAttempting to set preferred_bookmark_id to {different_bookmark.id} (belongs to UserWord {different_bookmark.user_word_id})")
print("This SHOULD raise a ValueError...")

try:
    user_word.preferred_bookmark_id = different_bookmark.id
    db.session.add(user_word)
    db.session.commit()
    print("\n❌ ERROR: No exception was raised! Validation is NOT working!")
    sys.exit(1)
except ValueError as e:
    print(f"\n✓ SUCCESS: Validation caught the error!")
    print(f"Error message: {e}")
    db.session.rollback()
    sys.exit(0)
except Exception as e:
    print(f"\n❌ ERROR: Unexpected exception: {type(e).__name__}: {e}")
    db.session.rollback()
    sys.exit(1)

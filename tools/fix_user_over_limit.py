#!/usr/bin/env python

"""
Script to remove excess scheduled words for a user who has more words
in learning than their max_words_to_schedule setting allows.

This keeps the most common words (lowest rank) and removes the rest.
"""

import sys
sys.path.insert(0, '/Users/gh/zeeguu/api')

from zeeguu.core.model import User, UserPreference, UserWord, Meaning, Phrase
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
from zeeguu.core.model import db
from zeeguu.api.app import create_app

app = create_app()

def fix_user_over_limit(email):
    with app.app_context():
        user = User.find(email)
        if not user:
            print(f'User {email} not found')
            return False

        print(f'User: {user.email}')

        # Get user's max limit
        max_words = UserPreference.get_max_words_to_schedule(user)
        print(f'Max words to schedule: {max_words}')

        # Get all scheduled words
        scheduled_words = BasicSRSchedule.scheduled_user_words(user)
        print(f'Current scheduled words: {len(scheduled_words)}')

        if len(scheduled_words) <= max_words:
            print('User is within limit, no action needed')
            return True

        excess = len(scheduled_words) - max_words
        print(f'Need to remove {excess} words')
        print()

        # Sort by rank (prioritize keeping common words)
        sorted_words = sorted(scheduled_words, key=lambda uw: (
            uw.meaning.origin.rank if uw.meaning.origin.rank else 1000000
        ))

        # Words to keep (most common)
        words_to_keep = sorted_words[:max_words]
        # Words to remove (least common)
        words_to_remove = sorted_words[max_words:]

        print(f'Keeping {len(words_to_keep)} most common words')
        print(f'Removing {len(words_to_remove)} least common words')
        print()

        print('Words to be removed:')
        for uw in words_to_remove[:10]:
            rank = uw.meaning.origin.rank if uw.meaning.origin.rank else 'None'
            print(f'  {uw.meaning.origin.content} (rank: {rank})')
        if len(words_to_remove) > 10:
            print(f'  ... and {len(words_to_remove) - 10} more')
        print()

        # Ask for confirmation
        response = input(f'Remove {len(words_to_remove)} schedule entries? (yes/no): ')
        if response.lower() != 'yes':
            print('Aborted')
            return False

        # Remove the schedules
        removed_count = 0
        for uw in words_to_remove:
            schedule = BasicSRSchedule.find(uw)
            if schedule:
                db.session.delete(schedule)
                removed_count += 1

        db.session.commit()
        print(f'Removed {removed_count} schedule entries')
        print('Done!')
        return True

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python fix_user_over_limit.py <email>')
        sys.exit(1)

    email = sys.argv[1]
    success = fix_user_over_limit(email)
    sys.exit(0 if success else 1)

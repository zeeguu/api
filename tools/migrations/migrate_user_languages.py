#!/usr/bin/env python
"""
    Script that migrates the users from UMR 0.8.1 to 0.9.0
    It goes through all the users in the database, grabs
    their learned_language and the languages of their sources
    and adds these languages to the user_language table.

"""

import zeeguu_core
from zeeguu_core.model import User, UserLanguage, RSSFeedRegistration

session = zeeguu_core.db.session

counter = 0

all_users = User.query.all()

for user in all_users:
    learned_languages = []

    # Grab the learned language and add it to learned_languages
    learned_languages.append(user.learned_language)

    # Go through the user sources
    user_feed_registrations = RSSFeedRegistration.feeds_for_user(user)

    for feed_reg in user_feed_registrations:
        # Try catch is needed because apparently there are NoneType feeds in registrations..
        try:
            feed = feed_reg.rss_feed
            feed_language = feed.language
            if feed_language not in learned_languages:
                learned_languages.append(feed_language)
        except Exception as e:
            print(e)

    for language in learned_languages:
        user_language = UserLanguage.find_or_create(session, user, language)
        user_language.reading_news = True
        session.add(user_language)

    print(f'Added user_languages for user user {user}')
    session.commit()


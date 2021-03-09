#!/usr/bin/env python

"""

   Script that updates the ArticlesCache

   To be called from a cron job.

"""

import zeeguu_core
from zeeguu_core.content_recommender.mixed_recommender import _reading_preferences_hash, \
    _recompute_recommender_cache_if_needed
from zeeguu_core.model import User, ArticlesCache

session = zeeguu_core.db.session


def hashes_of_existing_cached_preferences():
    """

        goes through the ArticleCache table and gets
        the distinct content_hashes

    :return:
    """
    query = session.query(ArticlesCache.content_hash.distinct())
    distinct_hashes = [each[0] for each in query.all()]
    return distinct_hashes


def clean_the_cache():
    ArticlesCache.query.delete()
    session.commit()


def recompute_for_users():
    """

        recomputes only those caches that are already in the table
        and belong to a user. if multiple users have the same preferences
        the computation is done only for the first because this is how
        _recompute_recommender_cache_if_needed does.

        To think about:
        - what happens when this script is triggered simultaneously
        with triggering _recompute_recommender_cache_if_needed from
        the UI? will there end up be duplicated recommendations?
        should we add a uninque constraint on (hash x article)?

        Note:

        in theory, the recomputing should be doable independent of users
        in practice, the _recompute_recommender_cache takes the user as input.
        for that function to become independent of the user we need to be
        able to recover the ids of the languages, topics, searchers, etc. from the
        content_hash
        to do this their ids would need to be comma separated

        OTOH, in the future we might still want to have a per-user cache
        because the recommendations might be different for each user
        since every user has different language levels!!!

    :param existing_hashes:
    :return:
    """
    already_done = []
    for user_id in User.all_recent_user_ids():
        try:
            user = User.find_by_id(user_id)
            reading_pref_hash = _reading_preferences_hash(user)
            if reading_pref_hash not in already_done:
                _recompute_recommender_cache_if_needed(user, session)
                zeeguu_core.logp(f"Success for {reading_pref_hash} and {user}")
                already_done.append(reading_pref_hash)
            else:
                zeeguu_core.logp(f"nno need to do for {user}. hash {reading_pref_hash} already done")
        except Exception as e:
            zeeguu_core.logp(f"Failed for user {user}")


def recompute_for_topics_and_languages():
    from zeeguu_core.model import Topic, Language

    for each in Topic.get_all_topics():
        each.all_articles()

    for each in Language.available_languages():
        each.get_articles()


if __name__ == '__main__':
    clean_the_cache()
    recompute_for_users()

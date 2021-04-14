"""

 Recommends a mix of articles from all the languages,
 sources, topics, filters, and searches.


"""

from sqlalchemy import not_, or_
from zeeguu_core import info, logger
from zeeguu_core.model import (
    Article,
    UserArticle,
    UserLanguage,
    TopicFilter,
    TopicSubscription,
    SearchFilter,
    SearchSubscription,
    ArticleWord,
    ArticlesCache,
    CohortArticleMap,
    Language,
)

from sortedcontainers import SortedList


def article_recommendations_for_user(user, count):
    """

            Retrieve :param count articles which are equally distributed
            over all the feeds to which the :param user is registered to.

            Fails if no language is selected.

    :return:

    """

    # Temporary fix for the experiment of Gabriel
    AIKI_USERS_COHORT_ID = 109
    if user.cohort_id == AIKI_USERS_COHORT_ID:
        return CohortArticleMap.get_articles_info_for_cohort(user.cohort)

    import zeeguu_core

    user_languages = Language.all_reading_for_user(user)
    if not user_languages:
        return [user.learned_language]

    reading_pref_hash = _reading_preferences_hash(user)
    _recompute_recommender_cache_if_needed(user, zeeguu_core.db.session)

    # two fast calls ot /articles/recommended might result in a race condition
    # in _recompute_recommender_cache;
    # race condition in _recompute_recommender_cache might result in
    # duplicates in the db; since this is being sunset for the elastic search
    # it's not worth fixing the race condition; instead we're simply
    # ensuring that duplicate articles are removed at this point
    all_articles = set(ArticlesCache.get_articles_for_hash(reading_pref_hash, count))

    all_articles = [
        each for each in all_articles if (not each.broken and each.published_time)
    ]
    all_articles = SortedList(all_articles, lambda x: x.published_time)

    return [
        UserArticle.user_article_info(user, article)
        for article in reversed(all_articles)
    ]


def article_search_for_user(user, count, search):
    """


    Retrieve the articles :param user: requested which fit the :param search:
    profile, for the selected sources of the user.

    :return:

    """

    all_articles = _get_user_articles_sources_languages(user, 2500)
    # We are just using the first and second word of the user's search now
    search_articles = _get_articles_for_search_term(search)

    if search_articles is None:
        final = []
    else:
        s = set(all_articles)
        final = [article for article in search_articles if article in s]
        if len(final) < 5:
            all_articles = _get_user_articles_sources_languages(user)
            s = set(all_articles)
            final = [article for article in search_articles if article in s]

    # Sort them, so the first 'count' articles will be the most recent ones
    final.sort(key=lambda each: each.published_time, reverse=True)

    return [UserArticle.user_article_info(user, article) for article in final[:count]]


def _recompute_recommender_cache_if_needed(user, session):
    """

            This method first checks if there is an existing hash for the
            user's content selection, and if so, is done. If non-existent,
            it retrieves all the articles corresponding with this configuration
            and stores them as ArticlesCache objects.

    :param user: To retrieve the subscriptions of the user
    :param session: Needed to store in the db

    """

    reading_pref_hash = _reading_preferences_hash(user)
    logger.info(f"Pref hash: {reading_pref_hash}")

    articles_hash_obj = ArticlesCache.check_if_hash_exists(reading_pref_hash)

    if articles_hash_obj is False:
        logger.info("Recomputing recommender cache...")
        _recompute_recommender_cache(reading_pref_hash, session, user)

    logger.info("No need to recomputed recommender cache.")


def _recompute_recommender_cache(
    reading_preferences_hash_code, session, user, article_limit=42
):
    """

    :param reading_preferences_hash_code:
    :param session:
    :param user:

    :param article_limit: set to something low ... say 42 when working in real time... ti's
    a bit slow otherwise. however, when caching offline you can save

    :return:
    """
    all_articles = _find_articles_for_user(user)

    for art in all_articles:
        cache_obj = ArticlesCache(art, reading_preferences_hash_code)
        session.add(cache_obj)
        session.commit()


def _find_articles_for_user(user):
    """
    This method gets all the topic and search subscriptions for a user.
    It then returns all the articles that are associated with these.

    :param user:
    :return:
    """

    user_languages = Language.all_reading_for_user(user)

    topic_subscriptions = TopicSubscription.all_for_user(user)

    search_subscriptions = SearchSubscription.all_for_user(user)

    subscribed_articles = _filter_subscribed_articles(
        search_subscriptions, topic_subscriptions, user_languages, user
    )

    return subscribed_articles


def _filter_subscribed_articles(
    search_subscriptions, topic_subscriptions, user_languages, user
):
    """
    :param subscribed_articles:
    :param user_filters:
    :param user_languages:
    :param user_search_filters:
    :return:

            a generator which retrieves articles as needed

    """

    from zeeguu_core.model import Topic

    user_search_filters = SearchFilter.all_for_user(user)

    # TODO: shouldn't this be passed down from upstream?
    total_article_count = 30
    per_language_article_count = total_article_count / len(user_languages)

    final_article_mix = set()
    for language in user_languages:
        print(f"language: {language}")

        query = Article.query
        query = query.order_by(Article.id.desc())
        query = query.filter(Article.language == language)
        query = query.filter(Article.broken == False)
        query = query.filter(Article.uploader_id == None)

        # speed up a bit the stuff
        # query = query.filter(Article.id > 500000)

        # 0. Ensure appropriate difficulty
        declared_level_min, declared_level_max = user.levels_for(language)
        lower_bounds = declared_level_min * 10
        upper_bounds = declared_level_max * 10

        query = query.filter(lower_bounds < Article.fk_difficulty)
        query = query.filter(Article.fk_difficulty < upper_bounds)

        # 1. Keywords to exclude
        # ==============================
        keywords_to_avoid = []
        for user_search_filter in user_search_filters:
            keywords_to_avoid.append(user_search_filter.search.keywords)
        print(f"keywords to exclude: {keywords_to_avoid}")

        for keyword_to_avoid in keywords_to_avoid:
            query = query.filter(
                not_(
                    or_(
                        Article.title.contains(keyword_to_avoid),
                        Article.content.contains(keyword_to_avoid),
                    )
                )
            )  # title does not contain keywords

        # 2. Topics to exclude / filter out
        # =================================
        user_filters = TopicFilter.all_for_user(user)
        to_exclude_topic_ids = [each.topic.id for each in user_filters]
        print(f"to exlcude topic ids: {to_exclude_topic_ids}")
        print(f"topics to exclude: {user_filters}")
        query = query.filter(
            not_(Article.topics.any(Topic.id.in_(to_exclude_topic_ids)))
        )

        # 3. Topics subscribed, and thus to include
        # =========================================
        ids_of_topics_to_include = [
            subscription.topic.id for subscription in topic_subscriptions
        ]
        # print(f"topics to include: {topic_subscriptions}")
        print(f"topics ids to include: {ids_of_topics_to_include}")
        # we comment out this line, because we want to do an or_between it and the
        # one corresponding to searches later below!
        # query = query.filter(Article.topics.any(Topic.id.in_(topic_ids)))

        # 4. Searches to include
        # ======================
        print(f"Search subscriptions: {search_subscriptions}")
        ids_for_articles_containing_search_terms = set()
        for user_search in search_subscriptions:
            search_string = user_search.search.keywords.lower()

            articles_for_word = ArticleWord.get_articles_for_word(search_string)

            ids_for_articles_containing_search_terms.update(
                [article.id for article in articles_for_word]
            )

        # commenting out this line, in favor of it being part of a merge later
        # query = query.filter(Article.id.in_(article_ids))

        if ids_of_topics_to_include or ids_for_articles_containing_search_terms:
            query = query.filter(
                or_(
                    Article.topics.any(Topic.id.in_(ids_of_topics_to_include)),
                    Article.id.in_(ids_for_articles_containing_search_terms),
                )
            )

        query = query.limit(per_language_article_count)
        final_article_mix.update(query.all())

    return final_article_mix


def _get_user_articles_sources_languages(user, limit=1000):
    """

    This method is used to get all the user articles for the sources if there are any
    selected sources for the user, and it otherwise gets all the articles for the
    current learning languages for the user.

    :param user: the user for which the articles should be fetched
    :param limit: the amount of articles for each source or language
    :return: a list of articles based on the parameters

    """

    user_languages = Language.all_reading_for_user(user)
    all_articles = []

    for language in user_languages:
        info(f"Getting articles for {language}")
        new_articles = language.get_articles(most_recent_first=True)
        all_articles.extend(new_articles)
        info(f"Added {len(new_articles)} articles for {language}")

    return all_articles


def _get_articles_for_search_term(search_term):
    search_terms = search_term.lower().split()

    individual_term_results = []

    for each in search_terms:
        individual_term_results.append(set(ArticleWord.get_articles_for_word(each)))

    return individual_term_results[0].intersection(*individual_term_results[1:])


def _reading_preferences_hash(user):
    """

            Method to retrieve the hash, as this is done several times.

    :param user:
    :return: articles_hash: ArticlesHash

    """
    user_filter_subscriptions = TopicFilter.all_for_user(user)
    filters = [topic_id.topic for topic_id in user_filter_subscriptions]

    user_topic_subscriptions = TopicSubscription.all_for_user(user)
    topics = [topic_id.topic for topic_id in user_topic_subscriptions]

    user_languages = Language.all_reading_for_user(user)

    user_search_filters = SearchFilter.all_for_user(user)

    search_filters = [search_id.search for search_id in user_search_filters]
    user_searches = SearchSubscription.all_for_user(user)

    searches = [search_id.search for search_id in user_searches]

    articles_hash = ArticlesCache.calculate_hash(
        user, topics, filters, searches, search_filters, user_languages
    )

    return articles_hash

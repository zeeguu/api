"""

Recommender that uses ElasticSearch instead of mysql for searching.
Based on mixed recommender.
Still uses MySQL to find relations between the user and things such as:
  - topics, language and user subscriptions.

"""

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, Q

from zeeguu.core.elastic.basic_ops import es_get_es_id_from_article_id
from zeeguu.core.elastic.elastic_query_builder import (
    build_elastic_recommender_query,
    build_elastic_search_query,
    build_elastic_more_like_this_query,
    build_elastic_search_query_for_videos,
)
from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from zeeguu.core.model import (
    Article,
    Video,
    TopicFilter,
    TopicSubscription,
    SearchFilter,
    SearchSubscription,
    UserArticle,
    UserVideo,
    Language,
    UserPreference,
)
from zeeguu.core.model.user_activitiy_data import UserActivityData
from zeeguu.core.util.timer_logging_decorator import time_this


def filter_hits_on_score(hits, score_threshold):
    return [h for h in hits if h["_score"] > score_threshold]


def _prepare_user_constraints(user):
    language = user.learned_language

    # Get user's CEFR level for filtering (e.g., "A1", "B2")
    user_cefr_level = user.cefr_level_for_learned_language()

    # 1. Unwanted user topics
    # ==============================
    user_search_filters = SearchFilter.all_for_user(user)
    unwanted_user_searches = []
    for user_search_filter in user_search_filters:
        unwanted_user_searches.append(user_search_filter.search.keywords)
    print(f"keywords to exclude: {unwanted_user_searches}")

    # 2. Topics to exclude / filter out
    # =================================
    excluded_topics = TopicFilter.all_for_user(user)
    topics_to_exclude = [
        each.topic.title for each in excluded_topics if each is not None
    ]
    print(f"Topics to exclude: {excluded_topics}")

    # 3. Topics subscribed, and thus to include
    # =========================================
    topic_subscriptions = TopicSubscription.all_for_user(user)
    topics_to_include = [
        subscription.topic.title
        for subscription in topic_subscriptions
        if subscription is not None
    ]
    print(f"Topics to include: {topic_subscriptions}")

    # 6. Wanted user topics
    # =========================================
    user_subscriptions = SearchSubscription.all_for_user(user)

    wanted_user_searches = []
    for sub in user_subscriptions:
        wanted_user_searches.append(sub.search.keywords)
    print(f"keywords to include: {wanted_user_searches}")

    # 7. User ignored sources
    # =========================================
    user_ignored_sources = UserActivityData.get_sources_ignored_by_user(user)

    return (
        language,
        user_cefr_level,
        _topics_to_string(topics_to_include),
        _topics_to_string(topics_to_exclude),
        _list_to_string(wanted_user_searches),
        _list_to_string(unwanted_user_searches),
        user_ignored_sources,
    )


def article_recommendations_for_user(
    user,
    count,
    page=0,
    articles_to_exclude=None,
    es_scale="1d",
    es_offset="1d",
    es_decay=0.6,
    score_threshold_for_search=5,
    maximum_added_search_articles=10,
):
    """
        Retrieve up to :param count + maximum_added_search_articles articles
        which are equally distributed over all the feeds to which the :param user
        is registered to.

        The articles are prioritized based on recency and the difficulty, preferring
        articles that are close to the users level.

        The search articles prioritize finding the searches the user has saved, so that
        these articles are still shown even if not tagged by the topics selected.

        Fails if no language is selected.

        :param articles_to_exclude: List of article IDs to exclude from results

    :return:

    """

    final_article_mix = []
    (
        language,
        user_cefr_level,
        topics_to_include,
        topics_to_exclude,
        wanted_user_searches,
        unwanted_user_searches,
        user_ignored_sources,
    ) = _prepare_user_constraints(user)

    es = Elasticsearch(ES_CONN_STRING)

    # Check if user has enabled disturbing content filtering
    filter_disturbing = UserPreference.is_filter_disturbing_content_enabled(user)

    # build the query using elastic_query_builder
    query_body = build_elastic_recommender_query(
        count,
        wanted_user_searches,
        unwanted_user_searches,
        language,
        user_cefr_level,
        es_scale,
        es_offset,
        es_decay,
        topics_to_include=topics_to_include,
        topics_to_exclude=topics_to_exclude,
        user_ignored_sources=user_ignored_sources,
        articles_to_exclude=articles_to_exclude,
        filter_disturbing=filter_disturbing,
        page=page,
    )

    res = es.search(index=ES_ZINDEX, body=query_body)
    hit_list = res["hits"].get("hits")
    # Handle both articles and videos in organic recommendations
    content_objects = [
        (
            _get_article_from_ES_hit(h)
            if "article_id" in h["_source"]
            else _get_video_from_ES_hit(h)
        )
        for h in hit_list
    ]
    final_article_mix.extend([c for c in content_objects if c is not None])

    # Get articles based on Search preferences and track which search matched
    articles_from_searches = []
    search_matches_by_source = {}  # Maps source_id -> list of matched search terms
    for search in wanted_user_searches.split():
        search_results = article_and_video_search_for_user(
            user,
            1,
            search,
            page,
            score_threshold=score_threshold_for_search,
            use_published_priority=True,
        )
        for article in search_results:
            if article.source_id not in search_matches_by_source:
                search_matches_by_source[article.source_id] = []
            if search not in search_matches_by_source[article.source_id]:
                search_matches_by_source[article.source_id].append(search)
        articles_from_searches += search_results

    # Combine organic recommendations with search results, deduplicating by source_id
    # (articles with the same source_id are the same content, just different CEFR levels)
    seen_source_ids = set()
    content = []
    for c in final_article_mix:
        if c is None or c.broken:
            continue
        if c.source_id not in seen_source_ids:
            seen_source_ids.add(c.source_id)
            content.append(c)

    # Add search results, skipping duplicates (limit to maximum_added_search_articles)
    added_from_search = 0
    for c in articles_from_searches:
        if added_from_search >= maximum_added_search_articles:
            break
        if c.source_id not in seen_source_ids:
            seen_source_ids.add(c.source_id)
            content.append(c)
            added_from_search += 1

    # Attach matched searches to content objects
    # Only tag articles that came from explicit search queries (not organic title matching)
    for c in content:
        if c.source_id in search_matches_by_source:
            c._matched_searches = search_matches_by_source[c.source_id]

    # Filter out articles uploaded by the user themselves
    # (teachers shouldn't see their own uploaded texts in their recommendations)
    content = [
        c for c in content
        if not (isinstance(c, Article) and c.uploader_id == user.id)
    ]

    # Filter out teacher-uploaded texts that are not currently shared with user's active cohorts
    # (students should only see teacher texts if they're currently in a cohort that has that text)
    from zeeguu.core.model.cohort_article_map import CohortArticleMap
    user_cohort_ids = [cohort.cohort_id for cohort in user.cohorts]
    if user_cohort_ids:
        cohort_article_ids = set(
            mapping.article_id
            for mapping in CohortArticleMap.query.filter(
                CohortArticleMap.cohort_id.in_(user_cohort_ids)
            ).all()
        )
    else:
        cohort_article_ids = set()

    content = [
        c for c in content
        if not (isinstance(c, Article) and c.uploader_id is not None and c.id not in cohort_article_ids)
    ]

    sorted_content = sorted(content, key=lambda x: x.published_time, reverse=True)

    return sorted_content


def video_recommendations_for_user(
    user,
    count,
    page=0,
):
    (
        language,
        user_cefr_level,
        topics_to_include,
        topics_to_exclude,
        wanted_user_searches,
        unwanted_user_searches,
        user_ignored_sources,
    ) = _prepare_user_constraints(user)

    es = Elasticsearch(ES_CONN_STRING)
    video_query = build_elastic_search_query_for_videos(
        count,
        wanted_user_searches,
        unwanted_user_searches,
        language,
        user_cefr_level,
        topics_to_include=topics_to_include,
        topics_to_exclude=topics_to_exclude,
        user_ignored_sources=user_ignored_sources,
        page=page,
    )

    video_res = es.search(index=ES_ZINDEX, body=video_query)

    video_list = _to_videos_from_ES_hits(video_res["hits"].get("hits"))
    return video_list


@time_this
def article_and_video_search_for_user(
    user,
    count,
    search_terms,
    page=0,
    es_time_scale="1d",
    es_time_offset="1d",
    es_time_decay=0.65,
    use_published_priority=False,
    score_threshold=0,
):

    (
        language,
        user_cefr_level,
        topics_to_include,
        topics_to_exclude,
        wanted_user_searches,
        unwanted_user_searches,
        _,
    ) = _prepare_user_constraints(user)

    # build the query using elastic_query_builder
    query_body = build_elastic_search_query(
        count,
        search_terms,
        language,
        user_cefr_level,
        es_time_scale,
        es_time_offset,
        es_time_decay,
        page,
        use_published_priority,
    )

    es = Elasticsearch(ES_CONN_STRING)
    res = es.search(index=ES_ZINDEX, body=query_body)
    hit_list = res["hits"].get("hits")

    if score_threshold > 0:
        hit_list = filter_hits_on_score(hit_list, score_threshold)

    content_objects = [
        (
            _get_article_from_ES_hit(h)
            if "article_id" in h["_source"]
            else _get_video_from_ES_hit(h)
        )
        for h in hit_list
    ]

    final_mix = [
        each for each in content_objects if each is not None and not each.broken
    ]

    return final_mix


def topic_filter_for_user(
    user,
    count,
    newer_than,
    media_type,
    max_duration,
    min_duration,
    difficulty_level,
    topic,
):
    from zeeguu.core.elastic.elastic_query_builder import get_cefr_levels_to_match

    es = Elasticsearch(ES_CONN_STRING)

    s = Search().query(Q("term", language=user.learned_language.code()))

    if newer_than:
        s = s.filter("range", published_time={"gte": f"now-{newer_than}d/d"})

    AVERAGE_WORDS_PER_MINUTE = 70

    if max_duration:
        s = s.filter(
            "range", word_count={"lte": int(max_duration) * AVERAGE_WORDS_PER_MINUTE}
        )

    if min_duration:
        s = s.filter(
            "range", word_count={"gte": int(min_duration) * AVERAGE_WORDS_PER_MINUTE}
        )

    if media_type:
        if media_type == "video":
            s = s.filter("term", video=1)
        else:
            s = s.filter("term", video=0)

    if topic != None and topic != "all":
        s = s.filter("match", topics=topic.lower())

    # Filter by user's CEFR level (use .keyword sub-field for exact matching)
    user_cefr_level = user.cefr_level_for_learned_language()
    levels_to_match = get_cefr_levels_to_match(user_cefr_level)
    s = s.filter("terms", **{"available_cefr_levels.keyword": levels_to_match})

    query = s.query

    query_with_size = {
        "size": count,
        "query": query.to_dict(),
        "sort": [{"published_time": "desc"}],
    }

    res = es.search(index=ES_ZINDEX, body=query_with_size)

    hit_list = res["hits"].get("hits")

    final_article_mix = _to_articles_from_ES_hits(hit_list)

    articles = [a for a in final_article_mix if a is not None and not a.broken]

    return articles


def _list_to_string(input_list):
    return " ".join([each for each in input_list]) or ""


def _topics_to_string(input_list):
    return ",".join(input_list)


def _get_video_from_ES_hit(hit):
    return Video.find_by_id(hit["_source"]["video_id"])


def _get_article_from_ES_hit(hit):
    return Article.find_by_id(hit["_source"]["article_id"])


def _to_articles_from_ES_hits(hits, with_score=False):
    articles = []
    for hit in hits:
        article = _get_article_from_ES_hit(hit)
        if with_score:
            articles.append((hit.get("_score", 0), article))
        else:
            articles.append(article)

    return articles


def _to_videos_from_ES_hits(hits, with_score=False):
    videos = []
    for hit in hits:
        video = _get_video_from_ES_hit(hit)
        if with_score:
            videos.append((hit.get("_score", 0), video))
        else:
            videos.append(video)
    return videos


def __find_articles_like(
    recommended_articles_ids: "list[int]",
    limit: int,
    article_age: int,
    language_id: int,
) -> "list[Article]":
    es = Elasticsearch(ES_CONN_STRING)
    fields = ["content", "title"]
    language = Language.find_by_id(language_id)
    like_documents = [
        {"_index": ES_ZINDEX, "_id": es_get_es_id_from_article_id(article_id)}
        for article_id in recommended_articles_ids
    ]
    #
    like_documents = [d for d in like_documents if d["_id"] is not None]

    mlt_query = build_elastic_more_like_this_query(
        language=language,
        like_documents=like_documents,
        similar_to=fields,
        cutoff_days=article_age,
    )

    res = es.search(index=ES_ZINDEX, body=mlt_query, size=limit)
    articles = _to_articles_from_ES_hits(res["hits"]["hits"])
    articles = [a for a in articles if a.broken == 0]
    return articles


def content_recommendations(user_id: int, language_id: int):
    query = UserArticle.all_liked_articles_of_user_by_id(user_id)

    user_likes = []
    for article in query:
        if article.article.language_id == language_id:
            user_likes.append(article.article_id)

    articles_to_recommend = __find_articles_like(user_likes, 20, 50, language_id)

    return articles_to_recommend


def get_user_info_from_content_recommendations(user, content_list):
    """
    Get user-specific info for content recommendations.

    Handles mixed content (articles + videos) and deduplicates articles.
    """
    articles = [c for c in content_list if type(c) is Article]
    videos = [c for c in content_list if type(c) is not Article]

    # Build a map of root_article_id -> matched_searches
    # root_id is stable across version swaps (parent_article_id for simplified, own id for originals)
    matched_searches_by_root = {}
    for article in articles:
        if hasattr(article, '_matched_searches'):
            root_id = article.parent_article_id or article.id
            matched_searches_by_root[root_id] = article._matched_searches

    results = UserArticle.article_infos(user, articles, select_appropriate=True)

    # Add matched_searches to results based on root article id
    for result in results:
        # Result might be a simplified version (has parent_article_id) or original
        root_id = result.get('parent_article_id') or result.get('id')
        if root_id and root_id in matched_searches_by_root:
            result['matched_searches'] = matched_searches_by_root[root_id]

    results.extend([UserVideo.user_video_info(user, v) for v in videos])

    return results

"""
The recommender/search queries deliberately do NOT narrow by CEFR level.

With on-demand simplification any article is readable at the learner's level, so
filtering on `available_cefr_levels` — which lists only the levels ALREADY
generated for an article — hid nearly the whole index from a learner (and hid
everything at all whenever LLM assessment was down). These tests pin that down so
the filter can't creep back in unnoticed; see build_elastic_recommender_query.
"""

import json

from zeeguu.core.elastic.elastic_query_builder import (
    build_elastic_recommender_query,
    build_elastic_search_query,
    build_elastic_search_query_for_videos,
    get_cefr_levels_to_match,
)


class FakeLanguage:
    name = "Danish"


def recommender_query():
    return build_elastic_recommender_query(
        20,
        user_topics="",
        unwanted_user_topics="",
        language=FakeLanguage(),
        es_scale="1d",
        es_offset="1d",
        es_decay=0.6,
        topics_to_include="",
        topics_to_exclude="",
        user_ignored_sources=[],
    )


def test_recommender_query_does_not_filter_by_cefr_level():
    assert "available_cefr_levels" not in json.dumps(recommender_query())


def test_recommender_query_still_filters_by_language():
    must = recommender_query()["query"]["function_score"]["query"]["bool"]["must"]
    assert {"match": {"language": "Danish"}} in must


def test_search_query_does_not_filter_by_cefr_level():
    query = build_elastic_search_query(20, "hygge", FakeLanguage())
    assert "available_cefr_levels" not in json.dumps(query)


def test_video_query_does_not_filter_by_cefr_level():
    # Videos are the sharpest case: document_from_video never writes an
    # available_cefr_levels field, so a terms filter on it matched no video ever.
    query = build_elastic_search_query_for_videos(
        20,
        user_topics="",
        unwanted_user_topics="",
        language=FakeLanguage(),
        topics_to_include="",
        topics_to_exclude="",
        user_ignored_sources=[],
        page=0,
    )
    assert "available_cefr_levels" not in json.dumps(query)


def test_cefr_levels_to_match_includes_the_compound_band_below():
    # Still used by tools/feed_delivery_health_check.py to probe per-level
    # assessment coverage.
    assert get_cefr_levels_to_match("A2") == ["A2", "A1/A2"]
    assert get_cefr_levels_to_match("A1") == ["A1"]

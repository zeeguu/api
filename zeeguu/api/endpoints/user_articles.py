import flask

from zeeguu.core.content_recommender import (
    article_recommendations_for_user,
    topic_filter_for_user,
    content_recommendations,
    get_user_info_from_content_recommendations,
)
from zeeguu.core.model import (
    UserArticle,
    Article,
    PersonalCopy,
    User,
    UserArticleBrokenReport,
    Language,
    UserLanguage,
)

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.json_result import json_result
from sentry_sdk import capture_exception
from . import api


from flask import request

MAX_ARTICLES_PER_TOPIC = 20


# ---------------------------------------------------------------------------
@api.route("/user_articles/recommended", methods=("GET",))
@api.route("/user_articles/recommended/<int:count>", methods=("GET",))
@api.route("/user_articles/recommended/<int:count>/<int:page>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def user_articles_recommended(count: int = 15, page: int = 0):
    """
    Home Page recomendation for the users.

    It prioritizes Difficulty and Recency so the users see
    new articles every day.

    It also includes articles from user's search subscriptions if they
    are relevant enough. The articles are then sorted by published date.

    URL parameters:
    - exclude_saved: if 'true', exclude saved articles from results

    Note: Hidden articles are always excluded from recommendations.
    """

    user = User.find_by_id(flask.g.user_id)

    # Recommend for the language the client asks for, falling back to the
    # user's persisted learned language. On a language switch the client sends
    # the new language here so the feed is correct immediately, without waiting
    # for (or racing) the separate user_settings save that persists it.
    requested_language_code = request.args.get("language", None)
    language = user.learned_language
    if requested_language_code:
        try:
            candidate = Language.find(requested_language_code)
            # Only honor a language the user actually studies. Otherwise the
            # downstream per-language CEFR lookup (UserLanguage row) misses and
            # the whole recommendation silently degrades to the no-CEFR DB
            # fallback. The switcher only offers active languages, which always
            # have a row, so this just guards against stray/hand-crafted codes.
            UserLanguage.with_language_id(candidate.id, user)
            language = candidate
        except Exception:
            language = user.learned_language

    # Get exclusion parameters from request args
    exclude_saved = request.args.get("exclude_saved", "false").lower() == "true"

    # Collect article IDs to exclude
    articles_to_exclude = []

    # Always exclude originals when the user has saved a simplified child of
    # them — the user moved past the original, recycling it is noise.
    saved_for_user = PersonalCopy.all_for(user)
    for article in saved_for_user:
        if article.parent_article_id:
            articles_to_exclude.append(article.parent_article_id)

    if exclude_saved:
        # Also exclude the saved articles themselves (and their parents,
        # already covered above for simplifications).
        for article in saved_for_user:
            articles_to_exclude.append(article.id)

    # Always exclude hidden articles from recommendations
    hidden_user_articles = (
        UserArticle.query.filter_by(user=user)
        .filter(UserArticle.hidden.isnot(None))
        .all()
    )
    hidden_article_ids = [ua.article_id for ua in hidden_user_articles]
    articles_to_exclude.extend(hidden_article_ids)

    # Exclude articles that the user has reported as broken
    user_reported_articles = UserArticleBrokenReport.query.filter_by(
        user_id=user.id
    ).all()
    reported_article_ids = [report.article_id for report in user_reported_articles]
    articles_to_exclude.extend(reported_article_ids)

    # Remove duplicates from the exclusion list
    articles_to_exclude = list(set(articles_to_exclude))

    try:
        content = article_recommendations_for_user(
            user, count, page, articles_to_exclude, language=language
        )
        print("Total content found: ", len(content))
    except Exception as e:
        # Elasticsearch failed, fall back to database query
        print(f"Elasticsearch unavailable, using DB fallback: {type(e).__name__}")
        from zeeguu.core.model.cohort_article_map import CohortArticleMap

        query = Article.query.filter_by(broken=0).filter_by(
            language_id=language.id
        )

        # Apply exclusions to the fallback query as well
        if articles_to_exclude:
            query = query.filter(Article.id.notin_(articles_to_exclude))

        content = query.order_by(Article.published_time.desc()).limit(20).all()

        # Filter out teacher-uploaded texts not in user's active cohorts
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
            article for article in content
            if not (article.uploader_id is not None and article.id not in cohort_article_ids)
        ]

    content_infos = get_user_info_from_content_recommendations(user, content)
    return json_result(content_infos)


@api.route("/user_articles/saved", methods=["GET"])
@api.route("/user_articles/saved/<int:page>", methods=["GET"])
@cross_domain
@requires_session
def saved_articles(page: int = None):
    user = User.find_by_id(flask.g.user_id)
    if page is not None:
        saves = PersonalCopy.get_page_for(user, page)
    else:
        saves = PersonalCopy.all_for(user)

    # Hide the original when the user has also saved a simplified child of
    # it — the simplified version is the one they actually want to read.
    parent_ids_with_saved_simpl = {
        a.parent_article_id for a in saves if a.parent_article_id is not None
    }
    saves = [a for a in saves if a.id not in parent_ids_with_saved_simpl]

    article_infos = UserArticle.article_infos(user, saves, select_appropriate=True)

    return json_result(article_infos)


@api.route("/user_articles/hidden", methods=["GET"])
@api.route("/user_articles/hidden/<int:page>", methods=["GET"])
@cross_domain
@requires_session
def hidden_articles(page: int = None):
    """
    Get all articles that the user has hidden from their feed.
    """
    user = User.find_by_id(flask.g.user_id)

    # Get all hidden user_articles
    hidden_user_articles = (
        UserArticle.query.filter_by(user=user)
        .filter(UserArticle.hidden.isnot(None))
        .order_by(UserArticle.hidden.desc())  # Most recently hidden first
        .all()
    )

    # Collect unique parent articles (deduplicate simplified versions)
    seen_ids = set()
    unique_articles = []
    for ua in hidden_user_articles:
        article = ua.article
        if article is None:
            continue
        # If it's a simplified version, use the parent article instead
        if article.parent_article_id and article.parent_article:
            article = article.parent_article
        # Deduplicate
        if article.id not in seen_ids:
            seen_ids.add(article.id)
            unique_articles.append(article)

    article_infos = UserArticle.article_infos(user, unique_articles, select_appropriate=True)

    return json_result(article_infos)


# ---------------------------------------------------------------------------
@api.route("/user_articles/topic_filtered", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def user_articles_topic_filtered():
    """
    recommendations based on filters coming from the UI
    """

    topic = request.form.get("topic")
    newer_than = request.form.get("newer_than", None)
    media_type = request.form.get("media_type", None)
    max_duration = request.form.get("max_duration", None)
    min_duration = request.form.get("min_duration", None)
    difficulty_level = request.form.get("difficulty_level", None)
    user = User.find_by_id(flask.g.user_id)

    articles = topic_filter_for_user(
        user,
        MAX_ARTICLES_PER_TOPIC,
        newer_than,
        media_type,
        max_duration,
        min_duration,
        difficulty_level,
        topic,
    )

    # Filter out hidden articles
    filtered_articles = UserArticle.filter_hidden_articles(user, articles)

    article_infos = UserArticle.article_infos(user, filtered_articles, select_appropriate=True)

    return json_result(article_infos)


# ---------------------------------------------------------------------------
@api.route("/user_articles/starred_or_liked", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def user_articles_starred_and_liked():
    user = User.find_by_id(flask.g.user_id)
    return json_result(UserArticle.all_starred_and_liked_articles_of_user_info(user))


# ---------------------------------------------------------------------------
@api.route("/user_articles/my_articles", methods=("GET",))
@api.route("/user_articles/my_articles/<int:count>", methods=("GET",))
@api.route("/user_articles/my_articles/<int:count>/<int:page>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def user_articles_my_articles(count: int = None, page: int = 0):
    """My Articles = the user's saves (PersonalCopy). Distinct from
    /user_articles/starred_or_liked, which keys off UserArticle rows and
    misses saves the user hasn't opened yet.

    Paginated when count is provided — sort + family-collapse happens over
    all saves first, then the slice is fed through article_infos (which
    tokenizes / fills caches and is the expensive bit)."""
    user = User.find_by_id(flask.g.user_id)
    return json_result(UserArticle.my_articles_info(user, count=count, page=page))


# ---------------------------------------------------------------------------
@api.route("/cohort_articles", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def user_articles_cohort():
    """
    get all articles for the cohort associated with the user
    """
    user = User.find_by_id(flask.g.user_id)
    return json_result(user.cohort_articles_for_user())


# ---------------------------------------------------------------------------
@api.route("/user_articles/foryou", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def user_articles_foryou():
    article_infos = []
    user = User.find_by_id(flask.g.user_id)
    try:
        articles = content_recommendations(user.id, user.learned_language_id)
        print("Sending CB recommendations")
    except Exception as e:
        import traceback

        traceback.print_exc()
        print("Failed with: ", e)
        capture_exception(e)
        # Usually no recommendations when the user has not liked any articles
        articles = []

    # Filter out hidden articles
    filtered_articles = UserArticle.filter_hidden_articles(user, articles)

    article_infos = UserArticle.article_infos(user, filtered_articles, select_appropriate=True)

    return json_result(article_infos)

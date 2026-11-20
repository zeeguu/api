"""
A0 dialogues for new Evergreen articles, written at the end of a crawl.

After a crawl of a language in LANGUAGES, each Evergreen article that crawl
downloaded gets one try at a dialogue (zeeguu.core.llm_services.a0_article_dialogue),
until PER_TOPIC_PER_DAY dialogues exist for its topic today. A few per topic a
day is plenty for the handful of A0 learners, and keeps the cost bounded however
many Evergreen articles arrive. One try only: a dropped dialogue is not retried
by later crawls.

Only off-peak for DeepSeek, which writes and checks them: peak costs double.
Articles crawled at a peak hour get no dialogue. At most PER_RUN per crawl, so
the crawler lock is not held long: each takes 2 to 6 LLM calls.

tools/write_a0_dialogues.py writes them for older articles, by hand.
"""

from collections import Counter
from datetime import datetime, time

from sqlalchemy import func, or_

from zeeguu.core.content_recommender.evergreen import _disturbing_ids, _evergreen_articles
from zeeguu.core.llm_services.a0_article_dialogue import CHECKER, WRITER, write_a0_dialogue
from zeeguu.core.model import Article
from zeeguu.core.model.article_dialogue import ArticleDialogue
from zeeguu.logging import log

LANGUAGES = {"da"}
PER_TOPIC_PER_DAY = 3
PER_RUN = 5

# DeepSeek's peak hours, UTC, on weekdays (as read on
# api-docs.deepseek.com/quick_start/pricing on 14 Oct 2026, see
# tools/eval_haiku_models.py). Outside them the price is half.
PEAK_HOURS_UTC = [(1, 4), (6, 10)]


def is_deepseek_peak(now_utc):
    if now_utc.weekday() >= 5:
        return False
    return any(start <= now_utc.hour < end for start, end in PEAK_HOURS_UTC)


def topic_of(article):
    """The one topic an article counts against: its lowest topic id, or None."""
    ids = [t.topic_id for t in article.topics]
    return min(ids) if ids else None


def candidates(language, count, keyword=None, after_article_id=None):
    """The newest Evergreen articles of the language with a summary, not
    disturbing, and without a dialogue yet; with `after_article_id`, only
    those saved after it."""
    query = _evergreen_articles(language).filter(Article.summary.isnot(None))
    if after_article_id is not None:
        query = query.filter(Article.id > after_article_id)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(or_(Article.title.ilike(pattern), Article.summary.ilike(pattern)))
    chosen = []
    # Pages of the newest, until enough pass the filters below.
    for page in range(20):
        batch = query.order_by(Article.id.desc()).offset(page * count * 2).limit(count * 2).all()
        if not batch:
            break
        ids = [a.id for a in batch]
        disturbing = _disturbing_ids(ids)
        has_dialogue = ArticleDialogue.article_ids_inspired_by(ids)
        chosen += [a for a in batch if a.id not in disturbing and a.id not in has_dialogue]
        if len(chosen) >= count:
            break
    return chosen[:count]


def dialogues_today_per_topic(language, now_utc):
    start_of_day = datetime.combine(now_utc.date(), time.min)
    inspiring = (
        Article.query.join(ArticleDialogue, ArticleDialogue.inspired_by_article_id == Article.id)
        .filter(ArticleDialogue.created_at >= start_of_day, Article.language_id == language.id)
        .all()
    )
    return Counter(topic_of(a) for a in inspiring)


def last_article_id(session):
    """Taken before a crawl: the articles after it are the ones it saved."""
    return session.query(func.max(Article.id)).scalar() or 0


def write_for_new_evergreen(session, language, after_article_id, now_utc=None, write=write_a0_dialogue):
    """Write and save the dialogues for the Evergreen articles saved after
    `after_article_id`; returns them. `write` is replaceable for tests."""
    now_utc = now_utc or datetime.utcnow()
    if language.code not in LANGUAGES:
        return []
    if is_deepseek_peak(now_utc):
        log(f"[a0 dialogues] {language.code}: DeepSeek peak hour, none this crawl")
        return []

    per_topic = dialogues_today_per_topic(language, now_utc)
    saved = []
    for article in candidates(language, count=100, after_article_id=after_article_id):
        if len(saved) >= PER_RUN:
            break
        topic = topic_of(article)
        if per_topic[topic] >= PER_TOPIC_PER_DAY:
            continue
        result = write(language.name, article.title, article.summary)
        if not result.accepted:
            log(f"[a0 dialogues] {article.id}: dropped ({result.skip_reason})")
            continue
        dialogue = ArticleDialogue.create(session, article, result.title, result.lines, WRITER, CHECKER)
        session.commit()
        per_topic[topic] += 1
        saved.append(dialogue)
        log(f"[a0 dialogues] {article.id}: saved as article {dialogue.article_id}")
    return saved

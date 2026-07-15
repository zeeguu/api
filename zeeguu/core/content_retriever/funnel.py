"""Demand-aware ingestion funnel (Task 5).

The crawler used to simplify articles until a *static* per-language cap was hit
(50/day/topic for da/fr/de, 20 for the rest) and then skip the rest. That made
the expensive LLM step supply-driven: German was ~29% of the crawl while barely
anyone read it, and dormant languages were simplified at the same rate as busy
ones.

This module makes the simplification budget *demand-driven*:

  * The **demand surface** is what active readers actually want -- the distinct
    ``(language, topic)`` buckets across the active cohort, deduped (one FR
    politics article stocks every FR-politics reader, so demand is per bucket,
    not per user). A reader with no topic subscription reads the whole language,
    so they raise demand for every topic in it.

  * A bucket with demand gets a quota that scales with its reader count, clamped
    into a sane band. A bucket with no demand gets nothing from the demand path.

  * A **pilot-light floor** keeps a handful of distinct topics warm in every
    *supported* language that currently has no active readers, so a brand-new
    learner (or the Romanian kiosk) never opens an empty feed. The floor is
    per-language and topic-diverse, not per-topic, so it stays cheap.

``FunnelBudget`` is the single object the crawler threads through; it holds the
demand surface plus the day's running counts and answers one question per
article: *does this article earn a simplification?*
"""

from collections import defaultdict
from datetime import datetime, timedelta

# --- Tunables ---------------------------------------------------------------

# A reader counts as "active" if seen within this many days. This is the one
# knob that defines the whole demand surface; see ``_active_reader_rows``.
ACTIVE_READER_DAYS = 30

# Per-(language, topic) daily simplification quota for a bucket that has demand.
# Scales with the number of active readers who want the bucket, clamped so a
# single reader still gets a usable feed and one popular bucket can't run away.
# readers 1-5 -> 20, 6-10 -> 30, 11-15 -> 40, 16+ -> 50 (matches the old da/fr
# top cap for high-demand buckets while starving nobody).
MIN_ACTIVE_QUOTA = 20
MAX_ACTIVE_QUOTA = 50
QUOTA_STEP = 10
READERS_PER_QUOTA_STEP = 5

# Pilot light: a *supported* language with no active readers still gets a few
# simplified articles a day, spread across distinct topics (diverse, not
# per-topic) so a future learner's first feed isn't empty. ~5 / language / day.
LANGUAGE_FLOOR_TOPICS = 5
FLOOR_PER_TOPIC = 1


def _active_quota(readers):
    """Demand quota for a bucket with ``readers`` active readers (readers >= 1)."""
    steps = (readers - 1) // READERS_PER_QUOTA_STEP
    return min(MAX_ACTIVE_QUOTA, MIN_ACTIVE_QUOTA + steps * QUOTA_STEP)


class DemandSurface:
    """What active readers want, deduped across the cohort.

    ``subscribed_readers`` maps ``(language_id, topic_id)`` -> count of distinct
    active readers subscribed to that topic in that language. ``unfiltered_readers``
    maps ``language_id`` -> count of distinct active readers with *no* topic
    subscription; those readers read every topic in the language, so they lend
    demand to all of its topics.
    """

    def __init__(self, subscribed_readers, unfiltered_readers):
        self.subscribed_readers = dict(subscribed_readers)
        self.unfiltered_readers = dict(unfiltered_readers)

    def readers_for(self, language_id, topic_id):
        """Distinct active readers who want this bucket (subscribers + all-topic readers)."""
        return self.subscribed_readers.get(
            (language_id, topic_id), 0
        ) + self.unfiltered_readers.get(language_id, 0)

    def demanded_topic_ids(self, language_id):
        """Topic ids explicitly subscribed to in this language.

        Empty when nobody subscribes to a *specific* topic here. That is
        ambiguous on its own -- it can mean "dormant" or "all-topic readers
        only" -- so pair it with ``unfiltered_readers`` / ``language_has_demand``.
        """
        return {
            topic for (lang, topic) in self.subscribed_readers if lang == language_id
        }

    def language_has_demand(self, language_id):
        """True if any active reader wants any topic in this language."""
        if self.unfiltered_readers.get(language_id, 0) > 0:
            return True
        return any(lang == language_id for (lang, _topic) in self.subscribed_readers)

    def summary(self):
        """Short human-readable line for crawl logs."""
        langs = set(self.unfiltered_readers) | {
            lang for (lang, _t) in self.subscribed_readers
        }
        return (
            f"{len(langs)} language(s) with demand, "
            f"{len(self.subscribed_readers)} subscribed bucket(s), "
            f"{sum(self.unfiltered_readers.values())} all-topic reader(s)"
        )


def _active_reader_rows(session, active_days):
    """(user_id, learned_language_id) for every currently-active reader.

    "Active" is defined here and nowhere else, so switching the definition
    (e.g. to readers who actually *opened* an article) is a one-function change.
    """
    from zeeguu.core.model.user import User

    cutoff = datetime.now() - timedelta(days=active_days)
    return (
        session.query(User.id, User.learned_language_id)
        .filter(User.last_seen >= cutoff)
        .filter(User.learned_language_id != None)  # noqa: E711 (SQLAlchemy needs != None)
        .all()
    )


def compute_demand_surface(session, active_days=ACTIVE_READER_DAYS):
    """Build the demand surface from the active cohort's language + topic subscriptions."""
    from zeeguu.core.model.topic_subscription import TopicSubscription

    active_rows = _active_reader_rows(session, active_days)
    if not active_rows:
        return DemandSurface({}, {})

    lang_by_user = {uid: lang for uid, lang in active_rows}

    subs_by_user = defaultdict(set)
    subs = (
        session.query(TopicSubscription.user_id, TopicSubscription.topic_id)
        .filter(TopicSubscription.user_id.in_(list(lang_by_user)))
        .all()
    )
    for uid, topic_id in subs:
        subs_by_user[uid].add(topic_id)

    subscribed_readers = defaultdict(int)
    unfiltered_readers = defaultdict(int)
    for uid, lang in active_rows:
        topics = subs_by_user.get(uid)
        if not topics:
            # No topic subscription -> reads the whole language.
            unfiltered_readers[lang] += 1
        else:
            for topic_id in topics:
                subscribed_readers[(lang, topic_id)] += 1

    return DemandSurface(subscribed_readers, unfiltered_readers)


class FunnelBudget:
    """The day's simplification budget for one crawl process.

    Threaded through ``download_from_feed`` -> ``download_feed_item``; the gate is
    a single ``should_simplify`` call per article, followed by ``record`` when the
    article is actually simplified. Replaces the old ``topic_simplification_counts``
    dict + static ``get_max_simplified_for_language`` cap.
    """

    def __init__(self, demand_surface, todays_counts=None, floor_topics_used=None):
        self.demand = demand_surface
        # {(language_id, topic_id): simplifications recorded so far today}
        self.counts = defaultdict(int, todays_counts or {})
        # {language_id: set(topic_id)} distinct topics already given a floor slot
        self.floor_topics_used = defaultdict(set, floor_topics_used or {})

    def quota_for(self, language_id, topic_id):
        """Demand-path quota for a bucket (0 when it has no demand; floor is separate)."""
        readers = self.demand.readers_for(language_id, topic_id)
        return _active_quota(readers) if readers > 0 else 0

    def should_simplify(self, language_id, article_topic_ids):
        """Decide whether an article earns a simplification.

        Returns ``(bool, reason)`` where reason is ``"demand"``, ``"floor"`` or
        ``"capped"``. An article with no topics can never match a bucket and is
        never simplified through the funnel (parity with the old cap, which only
        kicked in when there were topics to match).
        """
        if not article_topic_ids:
            # No topic means no bucket to match. Such an article is only wanted by
            # readers who read the whole language (no subscription); serve them,
            # otherwise skip (a topic-subscriber can never see it anyway). Old
            # behaviour simplified every untagged article -- that was the waste.
            if self.demand.unfiltered_readers.get(language_id, 0) > 0:
                return True, "no-topic"
            return False, "no-topics"

        # Demand path: simplify if ANY of the article's topics is under quota.
        for topic_id in article_topic_ids:
            if self.counts[(language_id, topic_id)] < self.quota_for(
                language_id, topic_id
            ):
                return True, "demand"

        # Pilot-light floor: only for supported languages with no demand at all,
        # and only enough to keep a handful of distinct topics warm.
        if not self.demand.language_has_demand(language_id):
            used = self.floor_topics_used[language_id]
            for topic_id in article_topic_ids:
                if topic_id in used:
                    if self.counts[(language_id, topic_id)] < FLOOR_PER_TOPIC:
                        return True, "floor"
                elif len(used) < LANGUAGE_FLOOR_TOPICS:
                    return True, "floor"

        return False, "capped"

    def record(self, language_id, article_topic_ids, reason):
        """Book a simplification against every topic on the article."""
        for topic_id in article_topic_ids:
            self.counts[(language_id, topic_id)] += 1
            if reason == "floor":
                self.floor_topics_used[language_id].add(topic_id)

    def language_simplification_headroom(self, language_id):
        """How many more simplifications this language can still absorb today.

        Drives the pre-download triage (Task 5, phase 3): if a language is fully
        satisfied we skip its feeds before paying any readability/download cost;
        if it has limited room we download only the best few titles.

        Returns ``None`` for "effectively unbounded" -- when any reader reads the
        whole language, every topic is wanted, so there is no small budget to
        prune against and the caller should just honour its own ``limit``.
        """
        demand = self.demand
        if demand.unfiltered_readers.get(language_id, 0) > 0:
            return None  # all-topic readers -> every topic wanted

        if not demand.language_has_demand(language_id):
            # Dormant supported language: only the pilot-light floor slots remain.
            used = len(self.floor_topics_used.get(language_id, ()))
            return max(0, LANGUAGE_FLOOR_TOPICS - used)

        # Specific topic subscriptions only: sum the remaining quota per bucket.
        headroom = 0
        for topic_id in demand.demanded_topic_ids(language_id):
            quota = self.quota_for(language_id, topic_id)
            headroom += max(0, quota - self.counts[(language_id, topic_id)])
        return headroom


# --- Pre-download title triage (phase 3) ------------------------------------

# When a language has limited headroom we still download a bit more than the
# strict remaining count, because a downloaded article's topic won't always land
# in an under-quota bucket. This slack keeps buckets from under-filling.
TRIAGE_OVERSHOOT = 2


def triage_keep_count(headroom, limit):
    """How many feed items to actually download, given today's headroom + the
    caller's per-feed ``limit``. ``headroom is None`` means unbounded -> ``limit``."""
    if headroom is None:
        return limit
    if headroom <= 0:
        return 0
    return min(limit, headroom * TRIAGE_OVERSHOOT)


def select_titles_to_download(titles, language_code, demand_topic_names, keep_count, ranker=None):
    """Pick the best ``keep_count`` of ``titles`` to download (best-N, not first-N).

    ``titles`` is the ordered list of candidate feed-item titles. Returns the
    *indices* (into ``titles``) to keep, best first. A cheap LLM ranks them by
    newsworthiness / learner-suitability / topic match / diversity; on ANY
    failure (no key, timeout, unparseable output) we fall back to first-N, i.e.
    the crawler's historical behaviour -- triage can only ever be an improvement,
    never a regression.
    """
    if keep_count <= 0:
        return []
    if len(titles) <= keep_count:
        return list(range(len(titles)))

    ranker = ranker or _rank_titles_with_llm
    try:
        indices = ranker(titles, language_code, demand_topic_names, keep_count)
        # Keep only valid, in-range, de-duplicated indices, preserving order.
        seen = set()
        clean = []
        for i in indices:
            if isinstance(i, int) and 0 <= i < len(titles) and i not in seen:
                seen.add(i)
                clean.append(i)
        if clean:
            return clean[:keep_count]
    except Exception as e:
        from zeeguu.logging import log

        log(f"   ⚠ Title triage failed ({e}); falling back to first-{keep_count}")
    return list(range(keep_count))


def _rank_titles_with_llm(titles, language_code, demand_topic_names, keep_count):
    """Ask the cheap LLM tier to pick the best ``keep_count`` title indices."""
    import json
    import re

    from zeeguu.core.llm_services.llm_service import UnifiedLLMService

    numbered = "\n".join(f"{i}. {t}" for i, t in enumerate(titles))
    interests = ", ".join(demand_topic_names) if demand_topic_names else "any general-interest news"
    prompt = (
        f"You curate a {language_code} news feed for language learners.\n"
        f"Our readers are interested in: {interests}.\n"
        f"From the numbered headlines below, choose the best {keep_count} to keep. "
        f"Favour genuine, timely news that matches the interests, is suitable for "
        f"language learning, and gives topic variety. Avoid clickbait, ads, and "
        f"near-duplicates.\n"
        f"Reply with ONLY a JSON array of the chosen numbers, best first, "
        f"e.g. [3, 0, 7].\n\n"
        f"{numbered}"
    )

    raw = UnifiedLLMService().generate_text(prompt, max_tokens=200, temperature=0.2)
    match = re.search(r"\[[^\]]*\]", raw)
    if not match:
        raise ValueError(f"no JSON array in LLM reply: {raw!r}")
    return [int(x) for x in json.loads(match.group(0))]

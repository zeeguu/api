"""
Reading evidence: how likely a learner already knows a word they translated,
judged by how they read it before and after. ADR 032 (docs/adr), and the
EuroCALL 2026 paper "Estimating receptive vocabulary from incidental reading
behavior", §4.2 -- this is its model, ported from extract_progression.py in
vocabulary-estimation-from-reading.

Each word (Snowball stem) carries one running score S in log-odds, replayed
over the learner's history in time order:

    clean encounter (read article containing the word):  S <- DECAY*S + ALPHA
    look-up in a read article:                           S <- DECAY*S - (ALPHA + BETA)
    look-up anywhere else:                               S <- DECAY*S - BETA

    P(known) = sigmoid(S); no evidence = 0.5.

A look-up in a read article cancels the +ALPHA its article already gave the
word, netting -BETA, as in the paper. The paper drops look-ups made outside a
read article (a skimmed article, an exercise, a preview); here they count as a
plain -BETA. The gate only ever errs by keeping a word out of practice, so any
sign the learner did not know it is worth taking.

The gate decides on the FORM: every meaning of a word the learner reads
fluently is gated (det = it / this / the). Reading cannot tell senses apart,
and meaning.frequency, an LLM label without context, cannot either. A
genuine second sense hidden this way comes back with its next look-up, since
look-ups count against every meaning of the form. Scheduling itself stays
per meaning.

Only the stems of the learner's own user_words are tracked: a word can only be
practised if it was translated, so those are the only words the gate can act
on (ADR 032, "gate scope").
"""

import math
from collections import defaultdict
from dataclasses import dataclass

from nltk.stem import SnowballStemmer

from zeeguu.core.util.text import split_words_from_text

ALPHA = 0.5  # per clean encounter
BETA = 1.0  # per look-up
DECAY = 0.9  # per event, so recent behaviour weighs more

# ADR 032 opens at 0.90, not the paper's 0.75: at 0.75 a fifth of practised
# words would be skipped, 28% of them answered wrongly at the first attempt.
# 0.90 takes about eight clean articles after a single look-up.
GATE_P_KNOWN = 0.90
GATE_LOG_ODDS = math.log(GATE_P_KNOWN / (1 - GATE_P_KNOWN))

# An article counts as read at 300 wpm or slower, and at least 30 s.
# Same definition as the paper (_common.PLAUSIBLY_READ).
MIN_READ_MS = 30_000
MS_PER_WORD = 200

# Look-ups that say the learner did not know the word. generated_example and
# user_added are not look-ups; NULL is legacy reading.
LOOKUP_SOURCES = ("reading", "exercise", "article_preview")

ARTICLE, LOOKUP_IN_READ_ARTICLE, LOOKUP_ELSEWHERE = 0, 1, 2

SNOWBALL = {
    "da": "danish",
    "de": "german",
    "en": "english",
    "es": "spanish",
    "fr": "french",
    "it": "italian",
    "nl": "dutch",
    "no": "norwegian",
    "pt": "portuguese",
    "ro": "romanian",
    "ru": "russian",
    "sv": "swedish",
    "hu": "hungarian",
    "fi": "finnish",
}


def p_known(log_odds):
    if log_odds is None:
        return None
    if log_odds >= 0:
        return 1.0 / (1.0 + math.exp(-log_odds))
    e = math.exp(log_odds)
    return e / (1.0 + e)


def stemmer_for(language_code):
    """Word form -> stem, or the bare form where Snowball has no stemmer.

    Apostrophes go first: the tokeniser drops them ("l'homme" -> "l", "homme").
    """
    strip = lambda w: w.lower().replace("'", "").replace("’", "")
    if language_code not in SNOWBALL:
        return strip
    stem = SnowballStemmer(SNOWBALL[language_code]).stem
    cache = {}

    def reduce(word):
        if word not in cache:
            cache[word] = stem(strip(word))
        return cache[word]

    return reduce


@dataclass
class WordEvidence:
    log_odds: float = 0.0
    clean_encounters: int = 0
    lookups: int = 0

    @property
    def p_known(self):
        return p_known(self.log_odds)


def replay(events):
    """Fold (time, kind, payload) events into {stem: WordEvidence}.

    An ARTICLE event's payload is the set of stems read in it; a look-up's is
    one stem. On equal times the article comes first: its look-ups happened
    while reading it.
    """
    evidence = defaultdict(WordEvidence)
    for _time, kind, payload in sorted(events, key=lambda e: (e[0], e[1])):
        if kind == ARTICLE:
            for stem in payload:
                e = evidence[stem]
                e.log_odds = DECAY * e.log_odds + ALPHA
                e.clean_encounters += 1
        else:
            e = evidence[payload]
            penalty = ALPHA + BETA if kind == LOOKUP_IN_READ_ARTICLE else BETA
            e.log_odds = DECAY * e.log_odds - penalty
            e.lookups += 1
            if kind == LOOKUP_IN_READ_ARTICLE and e.clean_encounters:
                e.clean_encounters -= 1  # the article's +1 was not clean after all
    return dict(evidence)


def reading_events(user, language, reduce, stems_of_interest):
    """The learner's reading history in `language` as replay() events,
    restricted to `stems_of_interest`."""
    from sqlalchemy import func, or_

    from zeeguu.core.model import Article, Bookmark, Meaning, Phrase
    from zeeguu.core.model.bookmark_context import BookmarkContext
    from zeeguu.core.model.context_type import ContextType
    from zeeguu.core.model.db import db
    from zeeguu.core.model.user_reading_session import UserReadingSession
    from zeeguu.core.model.user_word import UserWord

    sessions = (
        db.session.query(
            UserReadingSession.article_id,
            Article.word_count,
            func.sum(UserReadingSession.duration),
            func.min(UserReadingSession.start_time),
        )
        .join(Article, UserReadingSession.article_id == Article.id)
        .filter(UserReadingSession.user_id == user.id)
        .filter(Article.language_id == language.id)
        .group_by(UserReadingSession.article_id, Article.word_count)
        .all()
    )
    read_time = {
        article_id: first_start
        for article_id, word_count, total_ms, first_start in sessions
        if first_start
        and (total_ms or 0) >= max(MIN_READ_MS, (word_count or 0) * MS_PER_WORD)
    }

    lookups = (
        db.session.query(
            Phrase.content,
            Bookmark.time,
            Bookmark.is_mwe,
            Bookmark.reading_session_id,
            Bookmark.id,
            UserReadingSession.article_id,
        )
        .join(UserWord, Bookmark.user_word_id == UserWord.id)
        .join(Meaning, UserWord.meaning_id == Meaning.id)
        .join(Phrase, Meaning.origin_id == Phrase.id)
        .outerjoin(
            UserReadingSession, Bookmark.reading_session_id == UserReadingSession.id
        )
        .outerjoin(BookmarkContext, Bookmark.context_id == BookmarkContext.id)
        .outerjoin(ContextType, BookmarkContext.context_type_id == ContextType.id)
        .filter(UserWord.user_id == user.id)
        .filter(Phrase.language_id == language.id)
        .filter(Bookmark.time != None)
        .filter(
            or_(
                Bookmark.translation_source == None,
                Bookmark.translation_source.in_(LOOKUP_SOURCES),
            )
        )
        # Before api#789, practice re-anchors were labelled 'reading' too.
        .filter(or_(ContextType.type == None, ContextType.type != ContextType.EXAMPLE_SENTENCE))
        .all()
    )

    events = []
    # A multi-word selection says the learner needed help somewhere in the
    # phrase, not which word: its words get no evidence from that article.
    ambiguous = set()
    first_click = {}  # (stem, session) -> (time, article_id): one per session
    for content, time, is_mwe, session_id, bookmark_id, article_id in lookups:
        stems = {reduce(w) for w in split_words_from_text(content or "")}
        if is_mwe or len(stems) > 1:
            ambiguous |= {(s, article_id) for s in stems}
            continue
        for stem in stems & stems_of_interest:
            key = (stem, session_id or -bookmark_id)
            if key not in first_click or time < first_click[key][0]:
                first_click[key] = (time, article_id)

    for (stem, _session), (time, article_id) in first_click.items():
        kind = LOOKUP_IN_READ_ARTICLE if article_id in read_time else LOOKUP_ELSEWHERE
        events.append((time, kind, stem))

    article_ids = list(read_time)
    for i in range(0, len(article_ids), 200):
        chunk = article_ids[i : i + 200]
        for article_id, content in db.session.query(Article.id, Article.content).filter(
            Article.id.in_(chunk)
        ):
            stems = {reduce(w) for w in split_words_from_text(content or "")}
            stems &= stems_of_interest
            stems -= {s for s in stems if (s, article_id) in ambiguous}
            if stems:
                events.append((read_time[article_id], ARTICLE, stems))

    return events


def is_single_word(content):
    return len(split_words_from_text(content or "")) == 1


def update_reading_evidence(session, user, language):
    """Recompute reading_log_odds and known_from_reading for the learner's
    user_words in `language`.

    Replays the whole history every time: idempotent, and an article that
    only crosses the read threshold on a later visit is counted correctly.

    Returns [(user_word, WordEvidence)] for the words whose known_from_reading
    changed, for logging.
    """
    from zeeguu.core.model import Meaning, Phrase
    from zeeguu.core.model.bookmark_user_preference import UserWordExPreference
    from zeeguu.core.model.user_word import UserWord

    from sqlalchemy.orm import joinedload

    user_words = (
        UserWord.query.options(joinedload(UserWord.meaning).joinedload(Meaning.origin))
        .join(Meaning, UserWord.meaning_id == Meaning.id)
        .join(Phrase, Meaning.origin_id == Phrase.id)
        .filter(UserWord.user_id == user.id)
        .filter(Phrase.language_id == language.id)
        .all()
    )
    reduce = stemmer_for(language.code)

    stem_of = {}
    for user_word in user_words:
        origin = user_word.meaning.origin.content
        if is_single_word(origin):
            stem_of[user_word.id] = reduce(split_words_from_text(origin)[0])

    events = reading_events(user, language, reduce, set(stem_of.values()))
    evidence = replay(events)

    changed = []
    for user_word in user_words:
        stem = stem_of.get(user_word.id)
        word_evidence = evidence.get(stem) if stem else None
        log_odds = word_evidence.log_odds if word_evidence else None

        known = bool(
            word_evidence
            and log_odds >= GATE_LOG_ODDS
            # The learner asked for this word in exercises.
            and int(user_word.user_preference or 0)
            != UserWordExPreference.USE_IN_EXERCISES
        )

        if bool(user_word.known_from_reading) != known:
            changed.append((user_word, word_evidence))
        if user_word.reading_log_odds != log_odds or bool(user_word.known_from_reading) != known:
            user_word.reading_log_odds = log_odds
            user_word.known_from_reading = known
            session.add(user_word)

    return changed

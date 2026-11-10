"""
Generated example sentences as exercise contexts.

Exercises show a word in the sentence where the learner looked it up. On
10 Nov 2026 only 24% of the contexts waiting to be practiced made good
exercise sentences: a whole sentence, at or below the learner's level, and
short. The rest were fragments the reader cut short (it saves at most ~28
words), titles, of unknown level, long, or above the learner's level (an A2
learner shown B2 sentences looked up half of each, user 6885).

So an example at or below the learner's level is the default, and the
original stays only when it is good (why_not_a_good_exercise_context). The
original stays among the word's bookmarks, and the exercise arrows still
offer it as a past context. A context the learner picked with the arrows is
never switched (has_default_context).
"""

from zeeguu.core.model import Bookmark
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.model.example_sentence import ExampleSentence
from zeeguu.core.model.example_sentence_misfit import ExampleSentenceMisfit
from zeeguu.core.model.exercise import Exercise
from zeeguu.core.tokenization.word_position_finder import find_first_occurrence, find_word_positions_in_text
from zeeguu.logging import log

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
# For learners without a level: most are A2, and too easy beats too hard
EXAMPLE_FALLBACK_LEVEL = "A2"


def learner_example_level(user, language):
    """The level to write and pick examples at for this learner in `language`:
    their level (A0 reads as A1), or EXAMPLE_FALLBACK_LEVEL when none is set."""
    try:
        return user.cefr_level_for_language(language)
    except ValueError:
        return EXAMPLE_FALLBACK_LEVEL


def levels_up_to(cefr_level):
    """The CEFR levels at or below `cefr_level`, easiest first. A0 reads as A1.
    A level we don't know (a client can send any) reads as
    EXAMPLE_FALLBACK_LEVEL, not as all levels: callers sort the hardest first,
    and too easy beats too hard."""
    if cefr_level == "A0":
        cefr_level = "A1"
    if cefr_level not in CEFR_LEVELS:
        cefr_level = EXAMPLE_FALLBACK_LEVEL
    return CEFR_LEVELS[: CEFR_LEVELS.index(cefr_level) + 1]


def anchorable_examples(examples, word, language):
    """
    The generated examples in which `word` can be located, so a bookmark can
    anchor it. The others get no bookmark (see bookmark_for_example) and are
    not worth storing or showing.
    """
    usable = [example for example in examples if _may_contain(word, example["sentence"], language)]
    if len(usable) < len(examples):
        log(f"Dropped {len(examples) - len(usable)} generated examples without '{word}'")
    return usable


def _may_contain(word, sentence, language):
    """False only when the sentence was tokenized and the word isn't in it.
    find_first_occurrence also says "not found" when tokenizing fails, and
    a tokenizer problem shouldn't silently drop every generated example."""
    try:
        return bool(find_word_positions_in_text(word, sentence, language)["found_positions"])
    except Exception as e:
        log(f"Couldn't check for '{word}' in a generated example, keeping it: {e}")
        return True


def bookmark_for_example(session, user, user_word, example_sentence):
    """
    Find or create the bookmark that anchors the user word in a generated
    example sentence. Returns None if the word can't be located in it.
    """
    result = find_first_occurrence(
        user_word.meaning.origin.content,
        example_sentence.sentence,
        user_word.meaning.origin.language,
    )
    if not result["found"]:
        log(
            f"Example {example_sentence.id} doesn't contain "
            f"'{user_word.meaning.origin.content}': {result['error_message']}"
        )
        return None

    pos = result["position_data"]
    return Bookmark.find_or_create(
        session,
        user,
        user_word.meaning.origin.content,
        user_word.meaning.origin.language.code,
        user_word.meaning.translation.content,
        user_word.meaning.translation.language.code,
        example_sentence.sentence,
        None,  # article_id
        None,  # source_id
        sentence_i=pos["sentence_i"],
        token_i=pos["token_i"],
        total_tokens=pos["total_tokens"],
        c_sentence_i=pos["c_sentence_i"],
        c_token_i=pos["c_token_i"],
        context_identifier=ContextIdentifier(
            context_type=ContextType.EXAMPLE_SENTENCE,
            example_sentence_id=example_sentence.id,
        ),
        translation_source="generated_example",
        user_word=user_word,
    )


def is_fragment(bookmark):
    """The reader cut the sentence short on either side."""
    context = bookmark.context
    return bool(context and (context.left_ellipsis or context.right_ellipsis))


def only_usable_examples(query, cefr_level=None):
    """
    Narrows a query over ExampleSentence to the usable ones: without those
    the validator would not pass their meaning in (ExampleSentenceMisfit),
    and with `cefr_level`, only those at or below it. No ordering, so it also
    fits a GROUP BY (the nightly prefetch counts examples per meaning).
    """
    query = query.filter(~ExampleSentence.id.in_(ExampleSentenceMisfit.ids()))
    if cefr_level is None:
        return query
    return query.filter(ExampleSentence.cefr_level.in_(levels_up_to(cefr_level)))


def usable_examples_query(meaning_id, cefr_level=None):
    """
    The meaning's usable examples (only_usable_examples). With `cefr_level`,
    closest to it first: an A2 learner gets A2, then A1. Newest first within
    a level, because newer examples come from newer prompts and models (the
    v4 example prompt, the 19 Oct cleanup), so they are the likeliest to be
    right. A query, so callers can limit or count it.
    """
    query = only_usable_examples(
        ExampleSentence.query.filter(ExampleSentence.meaning_id == meaning_id), cefr_level
    )
    if cefr_level is None:
        return query.order_by(ExampleSentence.id.desc())
    # The level names sort as the levels do: "A1" < "A2" < ... < "C2"
    return query.order_by(ExampleSentence.cefr_level.desc(), ExampleSentence.id.desc())


def usable_examples(meaning_id):
    return usable_examples_query(meaning_id).all()


def _rank(cefr_level):
    """A1 -> 0 .. C2 -> 5; None for anything else. An assessment between two
    levels ("B1/B2") counts as the higher one."""
    if not cefr_level:
        return None
    ranks = [CEFR_LEVELS.index(level) for level in cefr_level.split("/") if level in CEFR_LEVELS]
    return max(ranks) if ranks else None


def learner_level(user_word):
    """The level to pick examples at for this word's learner, A1..C2."""
    return learner_example_level(user_word.user, user_word.meaning.origin.language)


def article_level(bookmark):
    """The level of the article the bookmark's sentence comes from, or None
    (no article, or not assessed). Same choice as Article.article_info:
    the effective assessment first, the legacy column otherwise."""
    article = bookmark.text.article if bookmark.text else None
    if not article:
        return None
    if article.cefr_assessment and article.cefr_assessment.effective_cefr_level:
        return article.cefr_assessment.effective_cefr_level
    return article.cefr_level


# Longer real sentences are mostly reading, not practice: on 10 Nov 2026 half
# of the whole article sentences waiting to be practiced were longer.
MAX_EXERCISE_SENTENCE_WORDS = 15

# Written at the learner's level when they were made
LEVEL_ADAPTED_CONTEXTS = {ContextType.LEVEL_ADAPTED_ARTICLE_SUMMARY, ContextType.LEVEL_ADAPTED_ARTICLE_TITLE}
# Their level is the article's
ARTICLE_CONTEXTS = {ContextType.ARTICLE_FRAGMENT, ContextType.ARTICLE_TITLE, ContextType.ARTICLE_SUMMARY}


def example_level(bookmark):
    """The level of the generated example a bookmark shows, or None."""
    from zeeguu.core.model.example_sentence_context import ExampleSentenceContext

    # .first(): a bookmark can carry more than one example link
    link = ExampleSentenceContext.query.filter(ExampleSentenceContext.bookmark_id == bookmark.id).first()
    return link.example_sentence.cefr_level if link else None


def why_not_a_good_exercise_context(bookmark, cefr_level):
    """
    None when the bookmark's context makes a good exercise sentence for a
    learner at `cefr_level`; otherwise why not: "fragment", "too long",
    "level unknown" or "above level".

    Good means a whole sentence, at most MAX_EXERCISE_SENTENCE_WORDS words,
    at or below the learner's level: an A2 learner sees A2, also in a
    generated example (most older examples were written at B1). A context of
    unknown level (a web page, a video, an unassessed article or example) is
    not good: an example at the learner's level is the safer choice.

    Generated examples are not held to the length: they are what a long
    sentence gets swapped for, and swapping one example for another over a
    few words would only churn.
    """
    context = bookmark.context
    context_type = context.context_type.type if context and context.context_type else None
    is_example = context_type == ContextType.EXAMPLE_SENTENCE
    if is_fragment(bookmark):
        return "fragment"
    if not is_example and len((bookmark.get_context() or "").split()) > MAX_EXERCISE_SENTENCE_WORDS:
        return "too long"
    if context_type in LEVEL_ADAPTED_CONTEXTS:
        return None
    if is_example:
        level = example_level(bookmark)
    elif context_type in ARTICLE_CONTEXTS:
        level = article_level(bookmark)
    else:
        return "level unknown"
    learner, context_rank = _rank(cefr_level), _rank(level)
    if learner is None or context_rank is None:
        return "level unknown"
    if context_rank > learner:  # even one level above is too much
        return "above level"
    return None


def next_unused_example_bookmark(session, user_word, skip_ids=(), max_level=None):
    """The bookmark of the first usable example that anchors the word and is
    neither the word's preferred context nor one of `skip_ids`, or None.
    With `max_level`, only examples at or below that level, closest first."""
    examples = usable_examples_query(user_word.meaning_id, max_level)
    for example in examples.all():
        bookmark = bookmark_for_example(session, user_word.user, user_word, example)
        if not bookmark or bookmark.id == user_word.preferred_bookmark_id or bookmark.id in skip_ids:
            continue
        # The tokenizer can disagree with find_first_occurrence (#618); only
        # an example the exercise can blank out is worth switching to.
        if bookmark.as_dictionary(with_context=True, with_context_tokenized=True).get("_unanchorable"):
            continue
        return bookmark
    return None


def replace_context_with_example(session, user_word):
    """
    Make an example at or below the learner's level the word's preferred
    context, unless the current one is a good exercise context. With no such
    example yet, the context stays (the nightly prefetch writes examples at
    the learner's level). Returns True if it swapped.
    """
    if not user_word.preferred_bookmark:
        return False
    level = learner_level(user_word)
    why = why_not_a_good_exercise_context(user_word.preferred_bookmark, level)
    if why is None:
        return False

    bookmark = next_unused_example_bookmark(session, user_word, max_level=level)
    return _switch_to(session, user_word, bookmark, f"CONTEXT {why}")


def _switch_to(session, user_word, bookmark, why):
    if not bookmark:
        return False
    log(
        f"[{why}] user_word {user_word.id}: bookmark "
        f"{user_word.preferred_bookmark.id} -> example bookmark {bookmark.id}"
    )
    user_word.preferred_bookmark = bookmark
    session.add(user_word)
    session.commit()
    return True


def has_default_context(user_word):
    """
    The word's context is still the one it got when the learner looked it up:
    its first bookmark (Bookmark.find_or_create makes that the preferred
    one). Any other was chosen, by the learner with the exercise arrows
    (/set_preferred_bookmark, /set_preferred_example) or by the system.
    """
    preferred = user_word.preferred_bookmark
    if not preferred:
        return False
    first = Bookmark.query.filter(Bookmark.user_word_id == user_word.id).order_by(Bookmark.id).first()
    return first is not None and first.id == preferred.id


def replace_contexts_not_good_for_exercise(session, user_words):
    """
    Swap contexts that are not good exercise sentences for generated examples
    at the learner's level (replace_context_with_example). A word that was
    already exercised is swapped only while it still has its default context:
    a context the learner picked with the arrows must not be switched back
    behind their back, but one they never touched is ours to improve.

    Returns the number of words swapped.
    """
    candidates = [uw for uw in user_words if uw.preferred_bookmark]
    if not candidates:
        return 0

    exercised_ids = {
        row.user_word_id
        for row in session.query(Exercise.user_word_id)
        .filter(Exercise.user_word_id.in_([uw.id for uw in candidates]))
        .distinct()
    }

    swapped = 0
    for user_word in candidates:
        user_word_id = user_word.id
        try:
            if user_word_id in exercised_ids and not has_default_context(user_word):
                continue
            if replace_context_with_example(session, user_word):
                swapped += 1
        except Exception as e:
            # Serving the original context is the old behavior; never fail the
            # exercise session over this. Each swap commits on its own
            # (Bookmark.find_or_create commits anyway), so this only drops
            # this word's half-done work. Roll back before anything touches
            # the session again: even reading user_word.id would raise.
            session.rollback()
            log(f"[CONTEXT] user_word {user_word_id} not swapped: {e}")

    return swapped

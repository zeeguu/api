"""
Generated example sentences as exercise contexts.

The reader saves at most ~28 words around a looked-up word, so in a long
sentence the saved context is a fragment ("...håndkikkert kan du se, at kun
en del af ..."). A fragment often misses what makes the sentence make sense,
so before a word's first exercise we swap such a context for one of the
word's generated example sentences. The fragment stays among the word's
bookmarks, and the exercise arrows still offer it as a past context.

The same goes for a whole sentence from an article written above the
learner's level: an A2 learner shown a B2 sentence in an exercise looks up
half of it (user 6885, 9 Nov 2026). Such a context gives way only to an
example at or below the learner's level.
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


def usable_examples_query(meaning_id, cefr_level=None):
    """
    The meaning's generated examples without those the validator would not
    pass the meaning in (ExampleSentenceMisfit). With `cefr_level`, only
    those at or below it, closest to it first: an A2 learner gets A2, then A1.
    Newest first within a level, because newer examples come from newer
    prompts and models (the v4 example prompt, the 19 Oct cleanup), so they
    are the likeliest to be right. A query, so callers can limit or count it.
    """
    query = ExampleSentence.query.filter(
        ExampleSentence.meaning_id == meaning_id,
        ~ExampleSentence.id.in_(ExampleSentenceMisfit.ids()),
    )
    if cefr_level is None:
        return query.order_by(ExampleSentence.id.desc())
    # The level names sort as the levels do: "A1" < "A2" < ... < "C2"
    return query.filter(ExampleSentence.cefr_level.in_(levels_up_to(cefr_level))).order_by(
        ExampleSentence.cefr_level.desc(), ExampleSentence.id.desc()
    )


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


def is_above_level(bookmark, cefr_level):
    """The bookmark's sentence comes from an article written above
    `cefr_level`. Even one level above is too much for an exercise sentence."""
    learner, article = _rank(cefr_level), _rank(article_level(bookmark))
    return learner is not None and article is not None and article > learner


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


def replace_fragment_with_example(session, user_word):
    """
    Make one of the word's generated examples its preferred context, if the
    current one is a fragment and an example that anchors the word exists.
    Returns True if it swapped.
    """
    if not user_word.preferred_bookmark or not is_fragment(user_word.preferred_bookmark):
        return False

    # Any example beats a fragment, but one at the learner's level beats the rest
    bookmark = next_unused_example_bookmark(
        session, user_word, max_level=learner_level(user_word)
    ) or next_unused_example_bookmark(session, user_word)
    return _switch_to(session, user_word, bookmark, "FRAGMENT-CONTEXT")


def replace_above_level_with_example(session, user_word):
    """
    Make an example at or below the learner's level the word's preferred
    context, if the current one comes from an article above that level.
    Returns True if it swapped.
    """
    level = learner_level(user_word)
    if not user_word.preferred_bookmark or not is_above_level(user_word.preferred_bookmark, level):
        return False

    bookmark = next_unused_example_bookmark(session, user_word, max_level=level)
    return _switch_to(session, user_word, bookmark, "ABOVE-LEVEL-CONTEXT")


def replace_context_with_example(session, user_word):
    return replace_fragment_with_example(session, user_word) or replace_above_level_with_example(
        session, user_word
    )


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


def replace_hard_contexts_before_first_exercise(session, user_words):
    """
    Swap fragment contexts, and sentences from articles above the learner's
    level, for generated examples, but only for words that have never been
    exercised: once a learner has seen a word's context they may have picked
    it themselves (nothing records that), and we must not switch it back
    behind their back.

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
        if user_word_id in exercised_ids:
            continue
        try:
            if replace_context_with_example(session, user_word):
                swapped += 1
        except Exception as e:
            # Serving the fragment is the old behaviour; never fail the
            # exercise session over this. Each swap commits on its own
            # (Bookmark.find_or_create commits anyway), so this only drops
            # this word's half-done work. Roll back before anything touches
            # the session again: even reading user_word.id would raise.
            session.rollback()
            log(f"[FRAGMENT-CONTEXT] user_word {user_word_id} not swapped: {e}")

    return swapped

"""
Generated example sentences as exercise contexts.

The reader saves at most ~28 words around a looked-up word, so in a long
sentence the saved context is a fragment ("...håndkikkert kan du se, at kun
en del af ..."). A fragment often misses what makes the sentence make sense,
so before a word's first exercise we swap such a context for one of the
word's generated example sentences. The fragment stays among the word's
bookmarks, and the exercise arrows still offer it as a past context.
"""

from zeeguu.core.model import Bookmark
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.model.example_sentence import ExampleSentence
from zeeguu.core.model.exercise import Exercise
from zeeguu.core.tokenization.word_position_finder import find_first_occurrence, find_word_positions_in_text
from zeeguu.logging import log


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


def replace_fragment_with_example(session, user_word):
    """
    Make one of the word's generated examples its preferred context, if the
    current one is a fragment and an example that anchors the word exists.
    Returns True if it swapped.
    """
    if not user_word.preferred_bookmark or not is_fragment(user_word.preferred_bookmark):
        return False

    examples = (
        ExampleSentence.query.filter(ExampleSentence.meaning_id == user_word.meaning_id)
        .order_by(ExampleSentence.id)
        .all()
    )
    for example in examples:
        bookmark = bookmark_for_example(session, user_word.user, user_word, example)
        if not bookmark:
            continue
        # The tokenizer can disagree with find_first_occurrence (#618); only
        # an example the exercise can blank out is worth switching to.
        if bookmark.as_dictionary(with_context=True, with_context_tokenized=True).get("_unanchorable"):
            continue
        log(
            f"[FRAGMENT-CONTEXT] user_word {user_word.id}: bookmark "
            f"{user_word.preferred_bookmark.id} -> example bookmark {bookmark.id}"
        )
        user_word.preferred_bookmark = bookmark
        session.add(user_word)
        session.commit()
        return True
    return False


def replace_fragments_before_first_exercise(session, user_words):
    """
    Swap fragment contexts for generated examples, but only for words that
    have never been exercised: once a learner has seen a word's context they
    may have picked it themselves (nothing records that), and we must not
    switch it back behind their back.

    Returns the number of words swapped.
    """
    fragment_words = [
        uw for uw in user_words if uw.preferred_bookmark and is_fragment(uw.preferred_bookmark)
    ]
    if not fragment_words:
        return 0

    exercised_ids = {
        row.user_word_id
        for row in session.query(Exercise.user_word_id)
        .filter(Exercise.user_word_id.in_([uw.id for uw in fragment_words]))
        .distinct()
    }

    swapped = 0
    for user_word in fragment_words:
        user_word_id = user_word.id
        if user_word_id in exercised_ids:
            continue
        try:
            if replace_fragment_with_example(session, user_word):
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

"""
Frequency slots: the practice slots go to the most frequent words.

The scheduler holds max_words_to_schedule words in practice and fills a
free slot with the most frequent waiting word. But a slot, once given, was
kept until the word was learned, so a heavy reader filled the slots on day
one and far more frequent words looked up later waited for weeks (Megavault
projects/villum/exercises-requests.md, R1).

When the learner turns on UserPreference.FREQUENT_WORDS_FIRST, a more
frequent waiting word takes the slot of a rarer word in practice. One exception: a word that has reached
level 2 keeps its slot, so the learner never sees a word they are getting
right vanish. A frequent word the learner already knows leaves practice for
good when they say so ("I know this word": study_choice KNOWN, unfit).

A plain function on records, tested without a database
(test_frequency_slots.py); basicSR.py does the queries.
"""

from dataclasses import dataclass

from zeeguu.core.model.phrase import Phrase

# From this level on, a word keeps its slot until it is learned.
LEVEL_THAT_KEEPS_ITS_SLOT = 2


@dataclass(frozen=True)
class SlotWord:
    """A user word, as far as practice slots are concerned."""

    user_word_id: int
    # phrase.rank of the meaning's origin (the rarest word, for a phrase);
    # None while not computed
    rank: int | None
    # user_word.level; ignored for waiting words
    level: int = 0


def _rank(word: SlotWord):
    return word.rank or Phrase.IMPOSSIBLE_RANK


def words_to_take_out(scheduled, waiting):
    """
    The scheduled words that give up their slot to a more frequent waiting
    word: the rarest one that can lose its slot goes to the most frequent
    waiting word, the next rarest to the next, and so on, while the waiting
    word is more frequent.
    """
    can_lose = sorted(
        (w for w in scheduled if (w.level or 0) < LEVEL_THAT_KEEPS_ITS_SLOT),
        key=_rank,
        reverse=True,
    )
    best_waiting = sorted(waiting, key=_rank)

    taken_out = []
    for out_word, in_word in zip(can_lose, best_waiting):
        if _rank(in_word) >= _rank(out_word):
            break
        taken_out.append(out_word)
    return taken_out

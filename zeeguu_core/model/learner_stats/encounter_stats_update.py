from datetime import datetime

from zeeguu_core.model.ranked_word import WordForm

# Note that this is not the best approach. It is too simplistic, since
# it does not take into account the fact that in what is now the context
# there might have been a word which was looked up previously.
# Thus, a better algo that takes into account a more global view of the
# problem is needed.


def update_encounter_stats_after_adding_a_bookmark(bookmark, user, language, db):
    from .encounter_stats import EncounterStats
    """
    The main thing:
    - go through the words in the context, and update their
    encounter statistics
    :return:
    """

    a = datetime.now()
    context_words = bookmark.split_words_from_context()
    for word in context_words:
        word_form = WordForm.find_or_create(word, language)
        stat = EncounterStats.find_or_create_wordform(user, word_form)
        stat.event_seen_but_not_looked_up()
        db.session.add(stat)
    db.session.commit()
    b = datetime.now()
    delta = b - a
    print(("calculating probabilities for user {1} and bookmark {2} took {0}ms".
           format(int(delta.total_seconds() * 1000),
                  user.id,
                  bookmark.id)))

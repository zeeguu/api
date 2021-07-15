#!/usr/bin/env python

"""

   Script that lists recent users

   To be called from a cron job.

"""
from sortedcontainers import SortedList
from zeeguu.core.model import User, Bookmark

from wordstats import Word

user = User.find_by_id(1890)
language = 'nl'

months_dict = dict()

for bookmark in Bookmark.query.filter_by(user=user):

    if not bookmark.origin.language.code == language:
        continue

    # if not bookmark.quality_bookmark():
    #     continue

    if len(bookmark.origin.word) < 4:
        continue

    date_key = bookmark.time.strftime("%y-%m")

    if date_key not in months_dict:
        months_dict[date_key] = SortedList(key=lambda x: x.rank)

    word_stats = Word.stats(bookmark.origin.word, language)

    if word_stats.rank == 100000:
        print("ignoring: " + bookmark.origin.word)
        print(word_stats.rank)
        continue

    # our user has a lot of het's
    # might make sense to keep a word only once

    if word_stats not in months_dict[date_key]:
        months_dict[date_key].add(word_stats)

for key in months_dict:

    len_for_month = len(months_dict[key])
    print(f"{key} -> {len_for_month}")

    lower_bounds = int(len_for_month / 4)
    upper_bounds = int(len_for_month / 4 * 3)
    WORDS_TO_CONSIDER = upper_bounds - lower_bounds

    if WORDS_TO_CONSIDER == 0:
        continue

    ranks = ""
    sum = 0
    for each in months_dict[key][lower_bounds:upper_bounds]:
        ranks += f" {each.klevel} {each.word}"
        sum += each.klevel

    print(f"avg: {sum/WORDS_TO_CONSIDER}")
    print(ranks)
    print("")

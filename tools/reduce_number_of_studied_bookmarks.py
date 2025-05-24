from datetime import datetime

from wordstats import Word

import zeeguu
from zeeguu.api.app import create_app
from zeeguu.core.content_retriever.parse_with_readability_server import (
    download_and_parse,
)
from zeeguu.core.model import User, Language, UserPreference
from zeeguu.core.word_scheduling.basicSR.basicSR import (
    BasicSRSchedule,
    DEFAULT_MAX_WORDS_TO_SCHEDULE,
)

app = create_app()
app.app_context().push()
db_session = zeeguu.core.model.db.session


def reduce_for_user(u):
    # we iterate over all the languages,
    for lang in Language.all():
        in_pipeline = BasicSRSchedule.scheduled_meanings(u, lang)
        in_pipeline.sort(
            key=lambda x: (
                x.level,
                -Word.stats(x.origin.content, x.origin.language.code).rank,
            ),
            reverse=True,
        )

        number_of_level_2_words = len([x for x in in_pipeline if x.level >= 2])
        words_to_keep = max(DEFAULT_MAX_WORDS_TO_SCHEDULE, number_of_level_2_words)
        # there are eight learners that have more than 40 advanced to level 2
        # we can not scare the hell out of them with 136, 60, 55, 45 words to learn
        # they'll see them later - their progress will not be lost... but for now,
        # we cap it to 30
        words_to_keep = min(words_to_keep, 30)

        # there are eight learners that have more than 40 advanced to level 2
        # we can not scare the hell out of them with 136, 60, 55, 45 words to learn
        # they'll see them later - their progress will not be lost... but for now,
        # we cap it to 30
        words_to_keep = min(words_to_keep, 30)

        to_keep = in_pipeline[1:words_to_keep]
        to_remove = in_pipeline[words_to_keep:]

        if len(in_pipeline) > 0:
            print(f"In Pipeline for {lang.name}: " + str(len(in_pipeline)))

        if (len(to_remove)) > 0:

            print(f">>>>> Keeping: {words_to_keep}")
            for bookmark in to_keep:
                print(
                    f"  "
                    f"{bookmark.user_meaning.meaning.origin.content} {Word.stats(bookmark.user_meaning.meaning.origin.content, bookmark.user_meaning.meaning.origin.language.code).rank} {bookmark.level}"
                )

            print(f">>>>> To Remove (first 10...): " + str(len(to_remove)))

            for bookmark in to_remove:
                print(
                    f"  {bookmark.user_meaning.meaning.origin.content} {Word.stats(bookmark.user_meaning.meaning.origin.content, bookmark.user_meaning.meaning.origin.language.code).rank} {bookmark.level}"
                )
                schedule = BasicSRSchedule.find_by_user_meaning(bookmark)
                db_session.delete(schedule)
                # if the bookmark was scheduled and was at a level higher than 1 then
                # we don't reset it. Leave it there. Otherwise, we are safe to do so.
                # there are only about five users who will in this way lose a handful of bookmarks
                if bookmark.level <= 1:
                    bookmark.level = 0
                db_session.add(bookmark)

            # input("press enter to continue")
            db_session.commit()


for u in User.find_all():
    # for u in [User.find_by_id(4175)]:
    print(f"\n\n]]]]]]] User: {u.name} {u.id} [[[[[[[ ")
    print(f"  last active: {u.date_of_last_bookmark()}")
    if u.date_of_last_bookmark() and u.date_of_last_bookmark() > datetime(2024, 1, 1):
        print("reducing for recent user:")
        reduce_for_user(u)

    # updating user preference
    print("Updating user preference: ")
    pref = UserPreference.find_or_create(
        db_session,
        u,
        UserPreference.MAX_WORDS_TO_SCHEDULE,
        DEFAULT_MAX_WORDS_TO_SCHEDULE,
    )
    print(pref)

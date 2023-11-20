from zeeguu.core.definition_of_learned import is_learned_based_on_exercise_outcomes
from zeeguu.core.model import Bookmark
from zeeguu.core.model import db


def print_bookmarks_that_are_learned_without_history(bookmarks):
    for bookmark in bookmarks:
        if bookmark.learned_time and not bookmark.sorted_exercise_log():
            print(bookmark)
            print(bookmark.compact_sorted_exercise_log())


def print_bookmarks_that_are_wrongly_learned(bookmarks):
    i = 0
    for bookmark in bookmarks:

        if not bookmark.learned_time:
            continue

        algo_result = is_learned_based_on_exercise_outcomes(bookmark)

        if bookmark.learned != algo_result:
            print(f"){i}) mismatch: {bookmark} DB={bookmark.learned} ALGO={algo_result}")

            print(bookmark.compact_sorted_exercise_log())
            print(" ")
            i += 1

            bookmark.learned = algo_result
            db.session.add(bookmark)

    print("committing all the changes to the DB")
    db.session.commit()


bookmarks = Bookmark.query.filter_by(user_id=534)
bookmarks = Bookmark.query.all()

print_bookmarks_that_are_wrongly_learned(bookmarks)

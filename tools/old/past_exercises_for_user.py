import datetime

from zeeguu.core.model import User, Exercise, Bookmark
from zeeguu.core.model.bookmark import bookmark_exercise_mapping
from zeeguu.core.model import db

# USER_ID = 2162
# USER_ID = 2145  # Fe
# USER_ID = 2134 #Victor
USER_ID = 534


def past_exercises_for(user_id):
    user = User.find_by_id(USER_ID)

    q = (
        db.session.query(Exercise)
        .join(bookmark_exercise_mapping)
        .join(Bookmark)
        .join(User)
        .filter(User.id == USER_ID)
        .order_by(Exercise.time)
    )

    for ex in q.all():
        bookmark = ex.get_bookmark()
        past = ""

        sorted_log = sorted(
            bookmark.exercise_log,
            key=lambda x: datetime.datetime.strftime(x.time, "%Y-%m-%d"),
            reverse=True,
        )

        corrects_in_a_row = 0
        for each in sorted_log:
            if each.time < ex.time:
                if each.outcome.outcome == "Correct":
                    corrects_in_a_row += 1
                else:
                    corrects_in_a_row = 0

                past += f"{each.time.day}/{each.time.month} {each.outcome.outcome} < "

        if ex.outcome.outcome == "Correct":
            corrects_in_a_row += 1
        else:
            corrects_in_a_row = 0

        if corrects_in_a_row:
            print(
                f"{ex.time.day}/{ex.time.month} {bookmark.origin.word}({bookmark.id}) {ex.outcome.outcome}:{corrects_in_a_row} < ({past})"
            )
        else:
            print(
                f"{ex.time.day}/{ex.time.month} {bookmark.origin.word}({bookmark.id}) {ex.outcome.outcome} < ({past})"
            )

        if bookmark.learned and ex.time == bookmark.learned_time:
            print("Learned!")
            print(" ")

    print("All Bookmarks")
    for bookmark in user.all_bookmarks():
        btime = datetime.datetime.strftime(bookmark.time, "%Y-%m-%d")
        print(
            f"{btime} "
            + ("[fit_for_study] " if bookmark.fit_for_study else "")
            + ("[Learned] " if bookmark.learned else "")
            + f"{bookmark.id} "
            + f"{bookmark.origin.word} / {bookmark.translation.word}"
        )

    print("")
    print("Bookmarks to Study")
    for bookmark in user.bookmarks_to_study():
        btime = datetime.datetime.strftime(bookmark.time, "%Y-%m-%d")
        print(
            f"{btime} "
            + ("[Quality] " if bookmark.quality_bookmark() else "")
            + ("[fit_for_study] " if bookmark.fit_for_study else "")
            + ("[Learned] " if bookmark.learned else "")
            + f"{bookmark.id} "
            + f"{bookmark.origin.word} / {bookmark.translation.word}"
        )


if __name__ == "__main__":
    past_exercises_for(USER_ID)

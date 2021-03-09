# Once upon a time, in Jan 2020 it turned out that
# we wanted to fix the fix for study and bookmark
# priorities for two reasons:
#
# - there was a bug in the bookmark quality and a
#   bookmark that was a subset of another would not
#   be correctly detected as such
#
# - there were too few examples with contexts of
#   20 words so we increased the context size to 42

from zeeguu_core.model import User
from zeeguu_core.word_scheduling.arts.bookmark_priority_updater import BookmarkPriorityUpdater
from zeeguu_core import db


def fix_bookmark_priorities(USER_ID):
    print(f"fixing for user {USER_ID}")
    user = User.find_by_id(USER_ID)

    all_users_bookmarks = user.all_bookmarks()
    for each in all_users_bookmarks:
        each.update_fit_for_study()
    db.session.commit()

    BookmarkPriorityUpdater.update_bookmark_priority(db, user)
    print(f"... OK for {len(all_users_bookmarks)} bookmarks")


for user in User.find_all()[700:]:
    try:
        fix_bookmark_priorities(user.id)
    except:
        print("... failed")

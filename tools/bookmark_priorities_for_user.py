import datetime

from zeeguu_core.model import User, Exercise, Bookmark, BookmarkPriorityARTS
from zeeguu_core.model.bookmark import bookmark_exercise_mapping
from zeeguu_core import db

USER_ID = 534

q = (db.session.query(BookmarkPriorityARTS).
     join(Bookmark).
     filter(Bookmark.user_id == USER_ID).
     filter(BookmarkPriorityARTS.bookmark_id == Bookmark.id).
     order_by(BookmarkPriorityARTS.priority.desc()))


for bookmark_priority in q.all()[:50]:
    print(bookmark_priority)

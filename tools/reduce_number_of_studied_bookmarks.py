from zeeguu.core.content_retriever.parse_with_readability_server import (
    download_and_parse,
)

from zeeguu.api.app import create_app
from zeeguu.core.model import User, Language
import zeeguu
from zeeguu.core.word_scheduling.basicSR.basicSR import (
    BasicSRSchedule,
    MAX_WORDS_IN_PIPELINE,
)

app = create_app()
app.app_context().push()
db_session = zeeguu.core.model.db.session


# u = User.find_by_id(534)
u = User.find_by_id(4607)
print(u.learned_language)
u.learned_language = Language.find("da")
db_session.add(u)
db_session.commit()

in_pipeline = BasicSRSchedule.scheduled_bookmarks(u)
in_pipeline.sort(key=lambda x: x.level, reverse=True)
to_keep = in_pipeline[1:MAX_WORDS_IN_PIPELINE]
to_remove = in_pipeline[MAX_WORDS_IN_PIPELINE:]


print("In Pipeline: " + str(len(in_pipeline)))

print(">>>>> To Remove: " + str(len(to_remove)))
for bookmark in to_remove:
    print(f"{bookmark.origin.word} {bookmark.origin.rank} {bookmark.level}")
    schedule = BasicSRSchedule.find_by_bookmark(bookmark)
    db_session.delete(schedule)
    db_session.commit()

print(">>>>> Keeping: ")
for bookmark in to_keep:
    print(f"{bookmark.origin.word} {bookmark.origin.rank} {bookmark.level}")
    # schedule = BasicSRSchedule.find_by_bookmark(bookmark)

# print("Due Today: " + str(len(BasicSRSchedule.bookmarks_due_today(u))))

print(">>>>> Due Today: ")
due_today = BasicSRSchedule.scheduled_bookmarks_due_today(u)
for bookmark in due_today:
    print(f"{bookmark.origin.word} {bookmark.origin.rank} {bookmark.level}")


print(">>>>> In pipeline")
in_pipeline = BasicSRSchedule.scheduled_bookmarks(u)
for bookmark in in_pipeline:
    print(f"{bookmark.origin.word} {bookmark.origin.rank} {bookmark.level}")

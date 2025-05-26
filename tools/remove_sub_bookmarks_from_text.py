import zeeguu
from zeeguu.core.model import Text, Bookmark
from zeeguu.api.app import create_app
from tqdm import tqdm
from time import time

CHECKPOINT_COMMIT_AFTER_ROWS = 1000


app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session


def is_bookmark_substring_of_any_and_same_user(
    list_bookmarks: list[Bookmark], b: Bookmark
):
    return any(
        [
            b.origin.content in each.origin.content
            and b.user_meaning.user_id == each.user_id
            for each in list_bookmarks
        ]
    )


start = time()
all_texts = db_session.query(Text).all()
counter_total_deleted_bookmarks = 0
counter_total_deleted_texts = 0
total_bookmarks = len(db_session.query(Bookmark).all())
skipped_bookmarks = 0
for i, t in tqdm(
    enumerate(all_texts[::-1]),
    total=len(all_texts),
    bar_format="{l_bar}{bar:10}{r_bar}{bar:-10b}",
):
    bookmarks_for_text = t.all_bookmarks_for_text()
    if len(bookmarks_for_text) == 0:
        print("-" * 20)
        print(f"Text {t.id} doesn't have any bookmarks! Deleting...")
        counter_total_deleted_texts += 1
        db_session.delete(t)
        continue
    text_bookmarks = sorted(
        bookmarks_for_text,
        key=lambda b: len(b.meaning.origin.content),
        reverse=True,
    )
    long_bookmarks_list = [text_bookmarks[0]]
    has_printed = False
    last_long_bookmark_list = 0
    for b in text_bookmarks[1:]:
        is_a_substring = is_bookmark_substring_of_any_and_same_user(
            long_bookmarks_list, b
        )
        if is_a_substring:
            if not has_printed:
                print("-" * 20)
                print("Context: ")
                print(t.content)
                print("Bookmarks in context: ")
                print(
                    [
                        (b.user_meaning.meaning.origin.content, b.user_meaning.user_id)
                        for b in text_bookmarks
                    ]
                )
            if len(long_bookmarks_list) > last_long_bookmark_list:
                print("Longest bookmarks in text: ")
                print(
                    [
                        (b.user_meaning.meaning.origin.content, b.user_meaning.user_id)
                        for b in long_bookmarks_list
                    ]
                )
                last_long_bookmark_list = len(long_bookmarks_list)
            print(
                f"Deleting: {b.user_meaning.meaning.origin.content} for user {b.user_meaning.user_id}"
            )
            counter_total_deleted_bookmarks += 1
            has_printed = True
            db_session.delete(b)
        else:
            long_bookmarks_list.append(b)
    if (i + 1) % CHECKPOINT_COMMIT_AFTER_ROWS == 0:
        print("#" * 20)
        print(f"Completed {i+1} out of {len(all_texts)}, commiting changes...")
        db_session.commit()
        print(f"Total deleted texts: {counter_total_deleted_texts}")
        print(f"Total deleted bookmarks: {counter_total_deleted_bookmarks}")


end = time() - start
print(f"Total deleted texts: {counter_total_deleted_texts} out of {len(all_texts)}")
print(
    f"Total deleted bookmarks: {counter_total_deleted_bookmarks} out of {total_bookmarks}, time taken: {end:.2f}"
)

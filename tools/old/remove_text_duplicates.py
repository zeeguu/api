from zeeguu.core.model import Text, Bookmark
from zeeguu.core.util.hash import text_hash

from zeeguu.core.model import db

all_texts = Text.query.order_by(Text.id.desc()).all()

removed = 0
for each in all_texts:
    # print(each.id)
    dups = Text.query.filter_by(content=each.content).all()
    if len(dups) > 1:
        print("duplicates")

        original = dups[0]
        print(original.id)
        print(original.article_id)
        print(original.content_hash)
        print("->" + original.content + "<-")
        referring_bookmarks = Bookmark.query.filter_by(text_id=original.id).all()
        for bm in referring_bookmarks:
            print(bm)

        for dup in dups[1:]:
            print("text that's going to be removed because it's duplicated")
            print(dup.id)
            print(dup.article_id)
            print(dup.content_hash)
            print("->" + dup.content + "<-")
            print(text_hash(dup.content))

            print("bookmarks being moved:")
            referring_bookmarks = Bookmark.query.filter_by(text_id=dup.id).all()
            for bm in referring_bookmarks:
                print(f"moving {bm.id}...")
                bm.text_id = original.id
                db.session.add(bm)

        print("deleting duplicate too...")
        db.session.delete(dup)
        print("comitting")
        db.session.commit()

        print("ONE LESS...")
        removed += 1
        print(f"removed till now: {removed}")
        # input("")

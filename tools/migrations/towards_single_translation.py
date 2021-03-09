import zeeguu_core
from zeeguu_core.model import Bookmark

session = zeeguu_core.db.session

all_bs = Bookmark.query.filter_by(translation_id=None).all()
fixed = []
i = 0
for b in all_bs:
    i += 1
    fixed.append(b.id)
    b.translation = b.translations_list[0]
    session.add(b)
    if i == 1000:
        print("fixed form: {0} to {1}".
              format(fixed[0], fixed[-1]))
        i = 0
        fixed = []
        session.commit()
        # input("continue?")
session.commit()

import zeeguu.core
from zeeguu.core.model import Bookmark

db_session = zeeguu.core.model.db.session

all_bs = Bookmark.query.filter_by(translation_id=None).all()
fixed = []
i = 0
for b in all_bs:
    i += 1
    fixed.append(b.id)
    b.translation = b.translations_list[0]
    db_session.add(b)
    if i == 1000:
        print("fixed form: {0} to {1}".format(fixed[0], fixed[-1]))
        i = 0
        fixed = []
        db_session.commit()
        # input("continue?")
db_session.commit()

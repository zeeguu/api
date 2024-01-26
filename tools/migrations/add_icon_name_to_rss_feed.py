import zeeguu.core
from zeeguu.core.model import Feed

db_session = zeeguu.core.model.db.session

feeds = Feed.query.all()

for each in feeds:
    each.icon_name = each.image_url.path.split("/")[-1]
    db_session.add(each)
    db_session.commit()
    print(each.icon_name)

import zeeguu.core
from zeeguu.core.model import RSSFeed

db_session = zeeguu.core.model.db.session

feeds = RSSFeed.query.all()

for each in feeds:
    each.icon_name = each.image_url.path.split("/")[-1]
    session.add(each)
    session.commit()
    print(each.icon_name)

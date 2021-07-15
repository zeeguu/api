import zeeguu.core
from zeeguu.core.model import RSSFeed

session = zeeguu.core.db.session

feeds = RSSFeed.query.all()

for each in feeds:
    each.icon_name = each.image_url.path.split('/')[-1]
    session.add(each)
    session.commit()
    print(each.icon_name)

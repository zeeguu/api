import zeeguu_core
from zeeguu_core.model import Article
from zeeguu_core.model import RSSFeed
from zeeguu_core.content_retriever.quality_filter import sufficient_quality_of_text, sufficient_quality
import os
from zeeguu_core import db

SOURCE = 'www.newscientist.com'
TERMINATOR = '…'
STARTER = 'Create an account for'

feed = [each for each in RSSFeed.query.all() if SOURCE in each.url.as_string()][0]

all_articles = Article.query.filter_by(broken=0).filter_by(rss_feed_id=feed.id).order_by(Article.published_time.desc()).all()

user_selected_all = False
for each in all_articles:
    if (each.content.endswith(TERMINATOR) or each.content.startswith(STARTER)):
        print (each.title)
        print (each.url)
        print (each.id)
        print ("============")
        print (each.content)
        print ("============")

        if not user_selected_all: 
            a = input('mark as bad? (y/a/other): ')

        if a == 'a':
            user_selected_all = True

        if user_selected_all or (a == 'y'):
            print ("marking as broken")
            each.vote_broken()
            db.session.add(each)
            db.session.commit()


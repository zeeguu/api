from zeeguu.core.model import Article
from zeeguu.core.model import Feed
from zeeguu.core.content_cleaning.content_cleaner import cleanup_non_content_bits
from zeeguu.core.model import db

SOURCE = 'www.theonion.com'

feed = [each for each in Feed.query.all() if SOURCE in each.url.as_string()][0]

all_articles = Article.query.filter_by(broken=0).filter_by(feed_id=feed.id).order_by(
    Article.published_time.desc()).all()

user_selected_all = False
for each in all_articles:

    cleaned_up = cleanup_non_content_bits(each.content)
    if (cleaned_up != each.content):
        print(each.title)
        print(each.url)
        print(each.id)
        print("============")
        print(each.content)
        print("============")
        print(cleaned_up)

        if not user_selected_all:
            a = input('clean up? (y/a/other): ')

        if a == 'a':
            user_selected_all = True

        if user_selected_all or (a == 'y'):
            each.content = cleaned_up
            db.session.add(each)
            db.session.commit()
            print("cleaned up")

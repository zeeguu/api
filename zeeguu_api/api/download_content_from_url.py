from . import api


@api.route("/preload_articles", methods=("GET",))
def preload_articles():
    from zeeguu.model import User, RSSFeedRegistration
    import watchmen
    feeds_already_seen = set()
    for u in User.query.all():
        if u.active_during_recent(days=30):
            print(f'-- PRELOADING the articles for user {u.name}')
            for each in RSSFeedRegistration.feeds_for_user(u):
                if each not in feeds_already_seen:
                    print(f'---- PRELOADING feed {each.rss_feed.title}')
                    for feed_item in each.rss_feed.feed_items():
                        url = feed_item['url']
                        try:
                            watchmen.article_parser.get_article(url)
                        except Exception as e:
                            print(str(e))
                            print(f'failed while retrieving {url}')

    return "OK"
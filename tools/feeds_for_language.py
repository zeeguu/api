from zeeguu.api.app import create_app
from zeeguu.core.feed_handler import FEED_TYPE

from zeeguu.core.model.feed import Feed
from zeeguu.core.model.language import Language

app = create_app()
app.app_context().push()


def print_feed(feed):
    feed_names = dict((v, k) for k, v in FEED_TYPE.items())

    feed_type = feed_names.get(feed.feed_type)
    print(f"  - ({feed_type}): {feed.title} ({feed.url.as_string()})")


language = Language.find(input("Language code: "))
all_feeds_for_language = Feed.query.filter_by(language_id=language.id).all()

active_feeds = [feed for feed in all_feeds_for_language if not feed.deactivated]
inactive_feeds = [feed for feed in all_feeds_for_language if feed.deactivated]

print(f"Feeds for {language.name}: ")
for feed in active_feeds:
    deactivated_status = "Deactivated" if feed.deactivated else ""
    print_feed(feed)

if inactive_feeds:
    print(f"Inactive feeds for {language.name}: ")
    for feed in inactive_feeds:
        print_feed(feed)

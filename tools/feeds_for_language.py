from zeeguu.api.app import create_app

from zeeguu.core.model import Language, Feed

app = create_app()
app.app_context().push()

language = Language.find(input("Language code: "))
all_italian_feeds = Feed.query.filter_by(language_id=language.id).all()

active_feeds = [feed for feed in all_italian_feeds if not feed.deactivated]
inactive_feeds = [feed for feed in all_italian_feeds if feed.deactivated]

print(f"Feeds for {language.name}: ")
for feed in active_feeds:
    deactivated_status = "Deactivated" if feed.deactivated else ""
    print(f"  - {feed.title} ({feed.url.domain_name()})")


if inactive_feeds:
    print(f"Inactive feeds for {language.name}: ")
    for feed in inactive_feeds:
        print(f"  - {feed.title} ({feed.url.domain_name()})")

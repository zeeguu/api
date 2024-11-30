from zeeguu.api.app import create_app

from zeeguu.core.model import Language, Feed

app = create_app()
app.app_context().push()

language = Language.find(input("Language code: "))
all_italian_feeds = Feed.query.filter_by(language_id=language.id).all()


print(f"Feeds for {language.name}: ")
for feed in all_italian_feeds:
    print(f"  - {feed.title} ({feed.url.domain_name()})")

from zeeguu.core.model import Feed, Url
from zeeguu.api.app import create_app
import zeeguu

db_session = zeeguu.core.model.db.session

app = create_app()
app.app_context().push()

feed_id = int(input("Current Feed ID: "))
feed = Feed.find_by_id(feed_id)

print(feed)
print(f"Found feed with title: {feed.title} and url: ")
print(feed.url.as_string())
print(feed.feed_health_info())

new_url = input("Input new feed url: ")
url_object = Url.find_or_create(db_session, new_url, feed.title)
feed.url = url_object
db_session.add(feed)
db_session.commit()

print("updated url: ")
print(feed.url.as_string())

print(feed.feed_health_info())

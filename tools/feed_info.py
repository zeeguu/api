#!/usr/bin/env python

from zeeguu.core.model import Feed
import zeeguu.core
from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session

url = input("Feed Url (or partof); leave empty if you don't search by it: ")
name = input("Feed Name (or partof) leave empty if you don't search by it: ")

all_feeds = Feed.query.all()
for feed in all_feeds:
    if (url and url in feed.url.as_string()) or (name and name in feed.title):
        print(f"id: {feed.id}")
        print(feed.title)
        print(feed.description)
        print(feed.language.code)
        print(feed.url.as_string())

#!/usr/bin/env python

from zeeguu.core.model import Feed, Url, Language
import zeeguu.core

RESOURCES_FOLDER = "https://zeeguu.unibe.ch/api/resources/"

name = input("Name of feed to update: ")

db_session = zeeguu.core.model.db.session

all_feeds = Feed.query.all()
for feed in all_feeds:
    if feed.title == name:
        print("Updating ... " + name)
        feed.title = input(f"Title ({feed.title}): ") or feed.title
        print(f"new title is: {feed.title}")
        _image_url = input("Icon file: ")
        feed.image_url = Url.find_or_create(db_session, RESOURCES_FOLDER + _image_url)
        print("new image url: " + feed.image_url.as_string())
        db_session.add(feed)
        db_session.commit()

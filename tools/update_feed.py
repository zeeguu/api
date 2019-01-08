#!/usr/bin/env python

from zeeguu_core.model import RSSFeed, Url, Language
import zeeguu_core

RESOURCES_FOLDER = "https://zeeguu.unibe.ch/api/resources/"

name = input ("Name of feed to update: ")

session = zeeguu_core.db.session

all_feeds = RSSFeed.query.all()
for feed in all_feeds:
    if feed.title == name:
        print("Updating ... " + name)
        feed.title = input (f'Title ({feed.title}): ') or feed.title
        print (f'new title is: {feed.title}')
        _image_url = input ('Icon file: ') 
        feed.image_url = Url.find_or_create(session, RESOURCES_FOLDER+_image_url)
        print ('new image url: ' + feed.image_url.as_string())
        session.add(feed)
        session.commit()


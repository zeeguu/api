#!/usr/bin/python

from zeeguu.model import Bookmark, Url, Language
import zeeguu

session = zeeguu.db.session

name = input("Text from bookmark: " )

all = Bookmark.query.all()
for b in all:
    if name in b.text.content:
        print (b)
        print ("good for study: " + str(b.good_for_study()))
        print ("quality: " + str(b.quality_bookmark()))
        print ("starred: " + str(b.starred))
        print (" ")

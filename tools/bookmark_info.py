#!/usr/bin/env python

from zeeguu_core.model import Bookmark, Url, Language
import zeeguu_core

session = zeeguu_core.db.session

name = input("Text from bookmark: " )

all = Bookmark.query.all()
for b in all:
    if name in b.text.content:
        print (b)
        print ("good for study: " + str(b.fit_for_study()))
        print ("quality: " + str(b.quality_bookmark()))
        print ("starred: " + str(b.starred))
        print (" ")

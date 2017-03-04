#!/usr/bin/env python
# -*- coding: utf8 -*-

import setuptools


setuptools.setup(
    name="zeeguu_api",
    version="0.1",
    packages=setuptools.find_packages(),
    include_package_data=True,
    zip_safe=False,
    author="Zeeguu Team",
    author_email="me@mir.lu",
    description="API for Zeeguu",
    keywords="second language acquisition api",
    install_requires=("flask>=0.10.1",
                      "Flask-SQLAlchemy",
                      "Flask-Assets",
                      "goose-extractor",
                      "cssmin",
                      "jsmin",
                      "flask-wtf",
                      "goslate",
                      "MySQL-python",
                      "regex",
                      "beautifulsoup4",
                      "feedparser")
)

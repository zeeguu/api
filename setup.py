#!/usr/bin/env python
# coding: utf8 -*-

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
    keywords="Second language acquisition api",
    dependency_links=[
            "git+https://github.com/mircealungu/zeeguu-core.git#egg=zeeguu",
            "git+https://github.com/mircealungu/python-translators.git#egg=python_translators",
        ],
    install_requires=("flask>=0.10.1",
                      "Flask-SQLAlchemy",
                      "Flask-Assets",
                      "flask_cors",
                      "mysqlclient",
                      "regex",
                      "beautifulsoup4",
                      "feedparser",
                      'zeeguu',
                      'python_translators')
)

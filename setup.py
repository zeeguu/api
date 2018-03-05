#!/usr/bin/env python
# coding: utf8 -*-

import setuptools

setuptools.setup(
    name="zeeguu_api",
    version="0.31",
    packages=setuptools.find_packages(),
    include_package_data=True,
    zip_safe=False,
    author="The Zeeguu Team",
    author_email="zeeguu.team@gmail.com",
    description="API for Zeeguu, a project that aims to accelerate vocabulary acquisition in a second language",
    keywords=" API, second language acquisition",
    dependency_links=[
        "https://github.com/zeeguu-ecosystem/Zeeguu-Core/tarball/master#egg=zeeguu",
        "https://github.com/zeeguu-ecosystem/Python-Translators/tarball/master#egg=python_translators"],
    install_requires=("flask>=0.10.1",
                      "Flask-SQLAlchemy",
                      "Flask-Assets",
                      "flask_cors",
                      "mysqlclient",
                      "regex",
                      "beautifulsoup4",
                      "feedparser",
                      'zeeguu',
                      'python_translators',
                      'flask_monitoringdashboard'

                      )
)

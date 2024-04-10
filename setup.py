#!/usr/bin/env python
# -*- coding: utf8 -*-
import setuptools
from setuptools.command.develop import develop
from setuptools.command.install import install


class DevelopScript(develop):
    def run(self):
        develop.run(self)
        ntlk_install_packages()


class InstallScript(install):
    def run(self):
        install.run(self)
        ntlk_install_packages()


def ntlk_install_packages():
    import nltk
    import os

    # install in /var/www if available
    # when API is run with mod_wsgi from container
    if os.path.exists("/var/www") and os.access("/var/www", os.W_OK):
        nltk.download("punkt", download_dir="/var/www/nltk_data/")
        nltk.download("averaged_perceptron_tagger", download_dir="/var/www/nltk_data/")
    else:
        print("Downloading nltk packages...")
        nltk.download("punkt")
        nltk.download("averaged_perceptron_tagger")


setuptools.setup(
    name="zeeguu_api",
    version="0.31",
    packages=setuptools.find_packages(),
    include_package_data=True,
    zip_safe=False,
    author="The Zeeguu Team",
    author_email="zeeguu.team@gmail.com",
    description=(
        "API for Zeeguu, a project that aims to accelerate vocabulary"
        " acquisition in a second language"
    ),
    keywords=" API, second language acquisition",
    cmdclass={
        "develop": DevelopScript,
        "install": InstallScript,
    },
)

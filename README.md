# Zeeguu-API ![Build Status](https://github.com/zeeguu-ecosystem/Zeeguu-API/actions/workflows/test.yml/badge.svg)

Zeeguu-API is an open API that allows tracking and modeling the progress of a learner in a foreign language with the
goal of recommending paths to accelerate vocabulary acquisition.

The API is also currently deployed as the backend for the [zeeguu.org](https://zeeguu.org) website.

## Overview

The API offers translations for the words that a learner encounters in their readings. The history of the translated
words and their context is saved and used to build a dynamic model of the user knowledge. The context is used to extract
the words the user knows and their topics of interest.

A teacher agent recommends the most important words to be studied next in order for the learner to accelerate his
vocabulary retention. This information can be used as input by language exercise applications, for example interactive
games.

A text recommender agent crawls websites of interest to the user and recommend materials to read which are in the zone
of proximal development.

## Read More

To read more about the API see
the [article](https://www.researchgate.net/publication/322489283_As_We_May_Study_Towards_the_Web_as_a_Personalized_Language_Textbook)
published about Zeeguu in the CHI'18 conference.

# Local Development Setup (macOS)

## Quick Start

```bash
./install.sh
```

This will install system dependencies (mysql-client), create a Python 3.12 virtual environment, install all pip packages, and download NLTK data.

## Prerequisites

- **macOS** with Homebrew
- **Python 3.12**: `brew install python@3.12`
- **MySQL client headers**: installed automatically by `install.sh`, or manually: `brew install mysql-client`

You also need these env vars in your shell profile (e.g. `~/.zprofile`):
```
export MYSQLCLIENT_CFLAGS="-I/opt/homebrew/opt/mysql-client/include/mysql/"
export MYSQLCLIENT_LDFLAGS="-L/opt/homebrew/opt/mysql-client/lib"
```

## Optional: Stanza NLP Models

After install, if you need language processing features:
```bash
source .venv/bin/activate
python install_stanza_models.py
```

# Docker Setup

For running via Docker instead of locally:

- copy `default.env` to `.env` and update `ZEEGUU_DATA_FOLDER`
- run `generate_configs.sh`
- run `docker compose up zapi_dev_translations`
- verify at `localhost:8080/available_languages`

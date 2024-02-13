# Zeeguu-API ![Build Status](https://github.com/zeeguu-ecosystem/Zeeguu-API/actions/workflows/test.yml/badge.svg)

Zeeguu-API is an open API that allows tracking and modeling the progress of a learner in a foreign language with the goal of recommending paths to accelerate vocabulary acquisition.

The API is also currently deployed as the backend for the [zeeguu.org](https://zeeguu.org) website.

## Overview

The API offers translations for the words that a learner encounters in their readings. The history of the translated words and their context is saved and used to build a dynamic model of the user knowledge. The context is used to extract the words the user knows and their topics of interest.

A teacher agent recommends the most important words to be studied next in order for the learner to accelerate his vocabulary retention. This information can be used as input by language exercise applications, for example interactive games.

A text recommender agent crawls websites of interest to the user and recommend materials to read which are in the zone of proximal development.

## Read More

To read more about the API see the [article](https://www.researchgate.net/publication/322489283_As_We_May_Study_Towards_the_Web_as_a_Personalized_Language_Textbook) published about Zeeguu in the CHI'18 conference.

# Development Notes

Once you clone the repo, please run:

    git config --local core.hooksPath .githooks/

This will make the rules in the .githooks/rules
folder be run before every commit. The rules
check for well-known bugs and code conventions.

# Prerequisites

1. Install `docker` on your machine. For Ubuntu you can run the following:

```sh
sudo apt-get install docker.io -y
```

# With MySQL Locally

This is useful for MacOS machines (M1 and later) on which MySQL does not seem to be running within docker

1. Create a zeeguu_test DB

- Create zeeguu_test:zeeguu_test user with access to the DB
- Import anonymized db data from ...

1. Build the `zeguu_api_dev` development image

   `docker build -f Dockerfile.development -t zeeguu_api_dev .`

2. Run the \_playground.py to ensure that you have something in the DB

   `docker-compose up dev_play`

   To ensure that the changes to the files on your local dev machine are reflected inside the container try to modify something in the `tools\_playground.py` file and rerun this command. Do you see the changes? That's good.

3. Run the development server inside of the container

   `docker-compose up dev_server`

   to test it open http://localhost:9001/available_languages in your browser and you should be able to see a list of language codes that are supported by the system

4. Test the deployment

   `docker-compose up dev_test`

### Note

Running from a docker image, at least on my M1 Max from 2021, is terribly slow. The `_playground.py` script takes 1s natively and 6s in Docker. Tests natively are 22s and in Docker are 280s!
So for running the development server this is ok, but for actual development, this might be quite annoying :(

# With MySQL in Separate Container

2. (Optional) Build docker images with the steps described [here](/docker/README.md).

3. Start mysql database by running a container with `zeeguu/zeeguu-mysql` image:

```sh
docker run --net=host --name=zeeguu-mysql -d zeeguu/zeeguu-mysql
```

Before continuing you should make sure the mysql database is ready to accept connections, otherwise zeeguu-api-core container will not start.
To check that, you can run:

```sh
$ docker logs zeeguu-mysql
...
2018-11-01T17:13:15.296779Z 0 [Note] Event Scheduler: Loaded 0 events
2018-11-01T17:13:15.296965Z 0 [Note] mysqld: ready for connections.
Version: '5.7.24'  socket: '/var/run/mysqld/mysqld.sock'  port: 3306  MySQL Community Server (GPL)
```

If you see the above lines at the end of the output then you are ready to proceed with the next steps.

4. Start Zeeguu API and Core by running a container with `zeeguu/zeeguu-api-core` image:

```sh
docker run --net=host --name=zeeguu-endpoints-core -d zeeguu/zeeguu-endpoints-core
```

You can check that the zeeguu-api-core container is started by running `docker ps`. You should see the following:

```sh
$ docker ps
CONTAINER ID        IMAGE                    COMMAND                  CREATED             STATUS              PORTS               NAMES
31373fb67f01        zeeguu/zeeguu-endpoints-core   "python zeeguu_api"      1 second ago        Up 1 second                             zeeguu-endpoints-core
0b988ad5956e        zeeguu/zeeguu-mysql      "docker-entrypoint.s…"   6 minutes ago       Up 6 minutes                            zeeguu-mysql
```

5. To make sure that the API works, you can call the `/available_languages` endpoint from a terminal like this:

   `curl 127.0.0.1:9001/available_languages`


7. If the answer is something like `["de", "es", "fr", "nl", "en"]` you have the API working.

Go have fun!


# Further Notes
## Running MySQL locally, not in a container on a mac

_(Mircea, Feb 2024)_

On Mac, if you want to run mysql locally, and not from within Docker, you need to install mysql-client with brew:  

```
brew install mysql-client
```

Mircea: On my M2 mac the `pip instal mysqlclient` (called indirectly via `pip install -r requirements`) still fails till I define the following: 

```
export MYSQLCLIENT_CFLAGS="-I/opt/homebrew/opt/mysql-client/include/mysql/"
export MYSQLCLIENT_LDFLAGS="-L/opt/homebrew/opt/mysql-client/lib -lmysqlclient"
```

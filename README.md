# Zeeguu-API [![Build Status](https://travis-ci.org/zeeguu-ecosystem/Zeeguu-API.svg?branch=master)](https://travis-ci.org/zeeguu-ecosystem/Zeeguu-API)


Zeeguu is an open API that allows tracking and modeling the progress of a learner in a foreign language with the goal of recommending paths to accelerate vocabulary acquisition.

The API offers translations for the words that a learner encounters in his readings. The history of the translated words and their context is saved and used to build a dynamic model of the user knowledge. The context is used to extract the words the user knows and their topics of interest.

A teacher agent recommends the most important words to be studied next in order for the learner to accelerate his vocabulary retention. This information can be used as input by language exercise applications, for example interactive games.

A text recommender agent crawls websites of interest to the user and recommend materials to read which are in the zone of proximal development.

The API is available at https://zeeguu.unibe.ch/api.

# Installation
1. Install [Zeeguu-Core](https://github.com/zeeguu-ecosystem/Zeeguu-Core). The API is a thin layer on top of it.
2. Clone this repo and run `python setup.py develop` from within the cloned folder. (Make sure to activate the `virtualenv` in which you installed Zeeguu-Core). 
3. Test that your installation works with: 

     `./run_tests.sh`

4. To try out the API run `export ZEEGUU_API_CONFIG=<path to config file> && python -m zeeguu_api`

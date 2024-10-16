#!/bin/bash

# Script that takes all the configuration info from .env and create the api.cfg and fmd.cfg
# configuration files tha are required for the API

export $(cat .env | xargs)
envsubst < default.api.cfg > api.cfg
envsubst < default.fmd.cfg > fmd.cfg


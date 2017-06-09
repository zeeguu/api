#!/bin/bash
scp $1 haddock.unibe.ch:/var/www/static

filename=$(basename $1)

ssh haddock.unibe.ch chmod o+r /var/www/static/$filename
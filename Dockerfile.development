FROM python:3.9.2-buster

RUN apt-get update
RUN apt-get upgrade -y


# Git
# ---
# required by github dependencies in requirements.txt
RUN apt-get -y install git


# mysql CL client
# -------------------------
# - good for debugging sometimes
RUN apt-get install -y mysql\*


# libmysqlclient
# --------------
# - required to be able to install mysqlclient with pip
#   https://stackoverflow.com/questions/5178292/pip-install-mysql-python-fails-with-environmenterror-mysql-config-not-found
RUN apt-get install -y default-libmysqlclient-dev

# Zeeguu-Api
# ----------

# Declare that this will be mounted from a volume
VOLUME /Zeeguu-API

# We need to copy the requirements file it in order to be able to install it
# However, we're not copying the whole folder, such that in case we make a change in the folder
# (e.g. to this build file) the whole cache is not invalidated and the build process does
# not have to start from scratch
RUN mkdir /Zeeguu-API
COPY ./requirements.txt /Zeeguu-API/requirements.txt
COPY ./setup.py /Zeeguu-API/setup.py

# Install requirements and setup
WORKDIR /Zeeguu-API

RUN python -m pip install -r requirements.txt
RUN python setup.py develop

# Copy the rest of the files 
# (this is done after the requirements are installed, so that the cache is not invalidated)
WORKDIR /Zeeguu-API
COPY . /Zeeguu-API

ENV ZEEGUU_CONFIG=/Zeeguu-API/default_docker.cfg

VOLUME /zeeguu-data 
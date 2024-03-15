FROM python:3.9.2-buster

RUN apt-get update

RUN apt-get upgrade -y

RUN mkdir /app

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

RUN python -m pip install -r requirements.txt

COPY . /app

RUN python setup.py
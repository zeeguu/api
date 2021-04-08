FROM python:3.9.2-buster

RUN apt-get update
RUN apt-get upgrade -y


# Git
# ---
# required by github dependencies in requirements.txt
RUN apt-get -y install git

RUN pip install pytest


# mysql CL client
# -------------------------
# - good for debugging sometimes
RUN apt-get install -y mysql\*


# libmysqlclient
# --------------
# - required to be able to install mysqlclient with pip
#   https://stackoverflow.com/questions/5178292/pip-install-mysql-python-fails-with-environmenterror-mysql-config-not-found
RUN apt-get install -y default-libmysqlclient-dev


# Apache
# ------
RUN apt-get install -y \
    apache2 \
    apache2-dev \
    vim


# mod_wsgi
# --------
RUN pip install mod_wsgi

RUN /bin/bash -c 'mod_wsgi-express install-module | tee /etc/apache2/mods-available/wsgi.{load,conf}'
RUN a2enmod wsgi
RUN a2enmod headers


RUN echo '\n\
<VirtualHost *:8080>\n\
    WSGIDaemonProcess zeeguu_api home=/zeeguu-data/ python-path=/Zeeguu-API/\n\
    WSGIScriptAlias / /Zeeguu-API/zeeguu_api.wsgi\n\
    <Location />\n\
        WSGIProcessGroup zeeguu_api\n\
	WSGIApplicationGroup %{GLOBAL}
    </Location>\n\
    <Directory "/Zeeguu-API">\n\
        <Files "zeeguu_api.wsgi">\n\
            Require all granted\n\
        </Files>\n\
    </Directory>\n\
    ErrorLog ${APACHE_LOG_DIR}/error.log\n\
    LogLevel info\n\
    CustomLog ${APACHE_LOG_DIR}/access.log combined\n\
</VirtualHost>' > /etc/apache2/sites-available/zeeguu-api.conf

RUN a2dissite 000-default.conf
RUN a2ensite zeeguu-api

# have apache listen on port 8080
RUN sed -i "s,Listen 80,Listen 8080,g" /etc/apache2/ports.conf

# reroute the access & error.log to stdout
# https://serverfault.com/questions/599103/make-a-docker-application-write-to-stdout
RUN ln -sf /dev/stdout /var/log/apache2/access.log \
    && ln -sf /dev/stderr /var/log/apache2/error.log



# FMD
# ---
#RUN pip install flask_monitoringdashboard
RUN git clone https://github.com/flask-dashboard/Flask-MonitoringDashboard/
WORKDIR Flask-MonitoringDashboard
RUN python setup.py develop



# Python Translators
# we can't rely on this being pulled automatically from GH by the requirements.txt
# some conflict between the install_requires and requirments.txt results in
# a mismatch between the google-api-python and six
# for the future it might still make sense to have a vendors folder and only
# map it in here; for debugging purposes it would be better than having to
# redeploy in case of needing to debug something
RUN git clone https://github.com/zeeguu-ecosystem/Python-Translators.git
WORKDIR Python-Translators
RUN python setup.py develop



# Zeeguu-Api
# ----------
COPY . /Zeeguu-API
RUN chown -R www-data:www-data /Zeeguu-API

WORKDIR /Zeeguu-API

RUN python -m pip install -r requirements.txt
RUN python setup.py develop


CMD  /usr/sbin/apache2ctl -D FOREGROUND


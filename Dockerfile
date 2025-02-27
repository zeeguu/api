FROM python:3.12.7

RUN apt-get clean all
RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get dist-upgrade -y

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

# ML: maybe better to map this file from outside?
RUN echo '\n\
<VirtualHost *:8080>\n\
    WSGIDaemonProcess zeeguu_api home=/zeeguu-data/ python-path=/Zeeguu-API/\n\
    WSGIScriptAlias / /Zeeguu-API/zeeguu_api.wsgi\n\
    <Location />\n\
        WSGIProcessGroup zeeguu_api\n\
	    WSGIApplicationGroup %{GLOBAL}\n\
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


# ML: is this needed?
RUN chown -R www-data:www-data /var/www


# have apache listen on port 8080
RUN sed -i "s,Listen 80,Listen 8080,g" /etc/apache2/ports.conf


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

# setup.py installs NLTK in the $ZEEGUU_RESOURCES_FOLDER folder, so we create it
RUN mkdir /zeeguu-resources
RUN chown -R :www-data $ZEEGUU_RESOURCES_FOLDER

# Allow rwx for group
RUN sudo chmod 770 $ZEEGUU_RESOURCES_FOLDER
# before it used to be 755... though I don't see
# Owner (root): Read, write, execute (7)
# Group (www-data): Read, write, execute (7)
# Others: Read and execute (5)
# Set Default Permissions for Future Files and Directories

RUN sudo setfacl -d -m g:www-data:rwx $ZEEGUU_RESOURCES_FOLDER



# Install requirements and run the setup.py
WORKDIR /Zeeguu-API

RUN python -m pip install -r requirements.txt
RUN python setup.py develop
    # this installs the nltk in the /zeeguu_resources/nltk_data


# but for the nltk to know where to look we need to set an envvar
ENV NLTK_DATA=$ZEEGUU_RESOURCES_FOLDER/nltk_data/


# Copy the rest of the files
# (this is done after the requirements are installed, so that the layer does not need to be changed
# if only the code is being changed...
COPY . /Zeeguu-API



# We can only run this here, after we copied the files,
# because it depends on the zeeguuu.core.languages
RUN python install_stanza_models.py


# Create the temporary folder for newspaper and make sure that it can be
# written by www-data
RUN mkdir /tmp/.newspaper_scraper
RUN chown -R :www-data /tmp/.newspaper_scraper
RUN sudo chmod 770 /tmp/.newspaper_scraper
RUN sudo setfacl -d -m g:www-data:rwx /tmp/.newspaper_scraper


ENV ZEEGUU_CONFIG=/Zeeguu-API/default_docker.cfg

VOLUME /zeeguu-data
VOLUME /zeeguu-resources

RUN a2dissite 000-default.conf
RUN a2ensite zeeguu-api



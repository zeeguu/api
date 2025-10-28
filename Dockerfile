FROM python:3.12.7

# Use BuildKit cache mount for apt to speed up package installation
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get clean all && \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get dist-upgrade -y

# Install all system packages in one layer with cache mount
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get install -y \
    acl \
    git \
    mysql* \
    default-libmysqlclient-dev \
    apache2 \
    apache2-dev \
    vim \
    ffmpeg


# mod_wsgi
# --------
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install mod_wsgi

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
RUN mkdir -p /Zeeguu-API
COPY ./requirements.txt /Zeeguu-API/requirements.txt
COPY ./setup.py /Zeeguu-API/setup.py

WORKDIR /Zeeguu-API

# Install requirements and run the setup.py
# Use BuildKit cache mount to persist pip cache between builds
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -r requirements.txt


# setup.py installs NLTK in the $ZEEGUU_RESOURCES_FOLDER folder, so we create it
ENV ZEEGUU_RESOURCES_FOLDER=/zeeguu-resources
RUN mkdir -p $ZEEGUU_RESOURCES_FOLDER




# Copy the rest of the files
# (this is done after the requirements are installed, so that the layer does not need to be changed
# if only the code is being changed...
COPY . /Zeeguu-API

RUN python setup.py develop #Installs the nltk resources in the /zeeguu_resources/nltk_data

# For nltk to know where to look we need to set an envvar inside of the image
ENV NLTK_DATA=$ZEEGUU_RESOURCES_FOLDER/nltk_data/


# We can only run this here, after we copied the files,
# because it depends on the zeeguuu.core.languages
RUN python install_stanza_models.py


# Create the temporary folder for newspaper and make sure that it can be
# written by www-data
ENV SCRAPER_FOLDER=/tmp/.newspaper_scraper
RUN mkdir -p $SCRAPER_FOLDER # -p does not report error if folder already exists


# Ensure that apache processes have acess to relevant folders
RUN chown -R www-data:www-data $SCRAPER_FOLDER
RUN chown -R www-data:www-data $ZEEGUU_RESOURCES_FOLDER


ENV ZEEGUU_CONFIG=/Zeeguu-API/default_docker.cfg

VOLUME /zeeguu-data

RUN a2dissite 000-default.conf
RUN a2ensite zeeguu-api



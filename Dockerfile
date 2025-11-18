FROM python:3.12.7

# Update and upgrade system packages
RUN apt-get clean all && \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get dist-upgrade -y

# Install system packages (removed Apache)
RUN apt-get install -y \
    acl \
    git \
    mysql* \
    default-libmysqlclient-dev \
    vim \
    ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Zeeguu-API setup
VOLUME /Zeeguu-API

# Copy requirements first for better layer caching
RUN mkdir -p /Zeeguu-API

# Install base requirements (heavy, rarely change) in separate layer
COPY ./requirements-base.txt /Zeeguu-API/requirements-base.txt
WORKDIR /Zeeguu-API
RUN python -m pip install --no-cache-dir -r requirements-base.txt

# Install app requirements (lighter, change more often) in separate layer
COPY ./requirements-app.txt /Zeeguu-API/requirements-app.txt
RUN python -m pip install --no-cache-dir -r requirements-app.txt

# Install gunicorn
RUN python -m pip install --no-cache-dir gunicorn

# Copy setup.py for later installation
COPY ./setup.py /Zeeguu-API/setup.py

# Setup NLTK resources folder
ENV ZEEGUU_RESOURCES_FOLDER=/zeeguu-resources
RUN mkdir -p $ZEEGUU_RESOURCES_FOLDER

# Copy the rest of the application
COPY . /Zeeguu-API

# Make entrypoint script executable
RUN chmod +x docker-entrypoint.sh

# Install the application
RUN python setup.py develop

# Set NLTK data path
ENV NLTK_DATA=$ZEEGUU_RESOURCES_FOLDER/nltk_data/

# Note: Stanza models are downloaded at runtime on first startup
# This allows them to persist in the volume and avoids build space issues

# Create temporary folder for newspaper scraper
ENV SCRAPER_FOLDER=/tmp/.newspaper_scraper
RUN mkdir -p $SCRAPER_FOLDER

# Set config path
ENV ZEEGUU_CONFIG=/Zeeguu-API/default_docker.cfg

# Data volume
VOLUME /zeeguu-data

# Expose port
EXPOSE 8080

# Run with entrypoint script that ensures models are downloaded before starting Gunicorn
# 4 workers (processes) with 15 threads each = 60 concurrent handlers
# --timeout 300 = 5 minute request timeout
# NOTE: --preload removed - causes database connection sharing across workers leading to deadlocks
# Each worker now initializes its own DB connections and Stanza models (slight memory overhead but safe)
CMD ["./docker-entrypoint.sh"]

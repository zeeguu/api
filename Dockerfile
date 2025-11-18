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
COPY ./requirements.txt /Zeeguu-API/requirements.txt
COPY ./setup.py /Zeeguu-API/setup.py

WORKDIR /Zeeguu-API

# Install Python requirements including gunicorn
# Use pip cache during install for speed, then purge to save space
RUN python -m pip install -r requirements.txt && \
    python -m pip install gunicorn && \
    python -m pip cache purge

# Setup NLTK resources folder
ENV ZEEGUU_RESOURCES_FOLDER=/zeeguu-resources
RUN mkdir -p $ZEEGUU_RESOURCES_FOLDER

# Copy the rest of the application
COPY . /Zeeguu-API

# Install the application
RUN python setup.py develop

# Set NLTK data path
ENV NLTK_DATA=$ZEEGUU_RESOURCES_FOLDER/nltk_data/

# Install Stanza models
RUN python install_stanza_models.py

# Create temporary folder for newspaper scraper
ENV SCRAPER_FOLDER=/tmp/.newspaper_scraper
RUN mkdir -p $SCRAPER_FOLDER

# Set config path
ENV ZEEGUU_CONFIG=/Zeeguu-API/default_docker.cfg

# Data volume
VOLUME /zeeguu-data

# Expose port
EXPOSE 8080

# Run with Gunicorn
# 4 workers (processes) with 15 threads each = 60 concurrent handlers
# --timeout 300 = 5 minute request timeout
# NOTE: --preload removed - causes database connection sharing across workers leading to deadlocks
# Each worker now initializes its own DB connections and Stanza models (slight memory overhead but safe)
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "4", \
     "--threads", "15", \
     "--timeout", "300", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info", \
     "zeeguu.api.app:create_app()"]

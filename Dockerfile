FROM python:3.12

# Install system packages (removed Apache)
# Note: Removed apt-get upgrade to enable Docker layer caching
# Using python:3.12 moving tag for automatic security updates
RUN apt-get update && \
    apt-get install -y \
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

# Install Python requirements with BuildKit cache mount
# Cache persisted via buildkit-cache-dance action to GitHub Actions cache
RUN --mount=type=cache,target=/root/.cache/pip \
    echo "=== Pip cache before install ===" && \
    ls -lah /root/.cache/pip 2>/dev/null || echo "Cache empty (first build)" && \
    python -m pip install -r requirements.txt && \
    python -m pip install gunicorn && \
    echo "=== Pip cache after install ===" && \
    du -sh /root/.cache/pip

# Setup NLTK resources folder
ENV ZEEGUU_RESOURCES_FOLDER=/zeeguu-resources
RUN mkdir -p $ZEEGUU_RESOURCES_FOLDER

# Copy the rest of the application
COPY . /Zeeguu-API

# Make entrypoint script executable
RUN chmod +x /Zeeguu-API/docker-entrypoint.sh

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

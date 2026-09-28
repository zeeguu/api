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

# uv installs the same requirements as pip, much faster. Pinned, so an uv
# release can't change a build under us.
COPY --from=ghcr.io/astral-sh/uv:0.8.0 /uv /uvx /bin/
# The cache is a mount, a different filesystem from site-packages: copy, don't
# try to hardlink. Compile bytecode at build time instead of at first import.
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1

# Zeeguu-API setup
VOLUME /Zeeguu-API

# Copy requirements first for better layer caching
RUN mkdir -p /Zeeguu-API
COPY ./requirements.txt /Zeeguu-API/requirements.txt
COPY ./setup.py /Zeeguu-API/setup.py

WORKDIR /Zeeguu-API

# Install Python requirements with a BuildKit cache mount (on the server it
# persists between builds; in CI buildkit-cache-dance carries it across runs)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r requirements.txt gunicorn

# Setup NLTK resources folder
# Use /zeeguu-data to match docker-compose volume mount
ENV ZEEGUU_RESOURCES_FOLDER=/zeeguu-data
RUN mkdir -p $ZEEGUU_RESOURCES_FOLDER

# Copy the rest of the application
COPY . /Zeeguu-API

# Make entrypoint script executable
RUN chmod +x /Zeeguu-API/docker-entrypoint.sh

# Install the application (editable: the source is bind-mounted over
# /Zeeguu-API at runtime). Replaces the deprecated `setup.py develop`, whose
# NLTK download wrote into /zeeguu-data inside the image, a path the runtime
# volume hides anyway; NLTK data lives on the /zeeguu-data volume.
RUN uv pip install --system --no-deps -e .

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

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py gunicorn.conf.py install_models.py docker-entrypoint.sh ./

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Stanza models directory - mount as volume for persistence
ENV STANZA_RESOURCE_DIR=/stanza_resources
RUN mkdir -p $STANZA_RESOURCE_DIR

# Expose port
EXPOSE 5001

# Health check. Tolerant timeout/retries: tokenization is CPU-bound and a long
# text can keep a worker busy, delaying /health. Aggressive values (5s/3) caused
# orchestrators (e.g. autoheal) to needlessly restart a healthy-but-busy service
# under load. Note: a compose-level healthcheck, if defined, overrides this.
HEALTHCHECK --interval=30s --timeout=30s --start-period=300s --retries=5 \
    CMD curl -f http://localhost:5001/health || exit 1

# Run with entrypoint that ensures models are downloaded
CMD ["./docker-entrypoint.sh"]

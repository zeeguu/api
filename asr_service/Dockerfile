FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY asr_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY asr_service/app.py asr_service/gunicorn.conf.py ./

EXPOSE 5002

HEALTHCHECK --interval=30s --timeout=5s --start-period=300s --retries=3 \
    CMD curl -f http://localhost:5002/health || exit 1

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]

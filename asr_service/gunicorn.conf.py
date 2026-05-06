import os


asr_service_port = os.environ.get("ASR_SERVICE_PORT", "80")
bind = os.environ.get("GUNICORN_BIND", f"0.0.0.0:{asr_service_port}")
workers = int(os.environ.get("GUNICORN_WORKERS", "1"))
threads = 1
preload_app = True

timeout = 120
graceful_timeout = 30

accesslog = "-"
errorlog = "-"
loglevel = "info"


def on_starting(server):
    print("ASR worker starting...")


def when_ready(server):
    print("ASR worker ready to accept connections")

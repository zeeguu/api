import os


bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:5002")
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

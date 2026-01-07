"""
Gunicorn configuration for Stanza service.

Key settings:
- preload_app=True: Load Stanza models in master process before forking.
  Workers share models via copy-on-write memory, drastically reducing RAM usage.
- workers=2: Fewer workers since tokenization is CPU-bound (not I/O bound).
  Adjust based on CPU cores and expected load.
"""

import os

# Server socket
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:5001")

# Worker processes - keep low since each worker loads all models (~8GB per worker)
workers = int(os.environ.get("GUNICORN_WORKERS", "1"))
threads = 1  # Single-threaded since Stanza isn't thread-safe

# DISABLED: preload_app causes PyTorch/Stanza to hang after fork
# Each worker loads models independently (more memory but works reliably)
preload_app = False

# Timeouts
timeout = 120  # Tokenization of long texts can take time
graceful_timeout = 30

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"


def on_starting(server):
    """Called before master process is initialized."""
    print("Stanza service starting...")


def post_fork(server, worker):
    """Called after a worker has been forked."""
    print(f"Worker {worker.pid} forked - sharing preloaded models via COW")


def when_ready(server):
    """Called when server is ready to accept connections."""
    print("Stanza service ready to accept connections")

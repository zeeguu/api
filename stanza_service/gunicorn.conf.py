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
    """Load every language model in this worker, before it serves traffic.

    preload_app=True would load once in the master and share via COW, but
    PyTorch hangs when a model loaded before fork is used after it. Loading
    here costs memory (no sharing) but is the one place that avoids the fork
    problem while still keeping models off the request path.

    Without this, models load lazily on first request per language per worker,
    under a global _PIPELINE_LOAD_LOCK -- so one cold language stalls every
    concurrent request in that worker. Production logged 11 such loads and 177
    STANZA-SLOW entries in 24h, including "tokenize took 5.0s for 47 chars".
    """
    print(f"Worker {worker.pid} forked - preloading Stanza models")
    try:
        from app import preload_all_models

        preload_all_models()
        print(f"Worker {worker.pid} ready with models preloaded")
    except Exception as e:
        # Serving with lazy loading is slow but correct; refusing to start is not.
        print(f"Worker {worker.pid}: model preload failed ({e}); falling back to lazy loading")


def when_ready(server):
    """Called when server is ready to accept connections."""
    print("Stanza service ready to accept connections")

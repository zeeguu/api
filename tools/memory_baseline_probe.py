"""
Where does an API worker's memory go before it serves a single request?

Replays what a gunicorn worker does at boot (imports, then create_app) in a
fresh process and prints the RSS after each step, so the per-worker baseline
can be attributed to a stage instead of guessed at. Wordstats preloading is
stubbed out (its ~1 GB is already accounted for) and so is Stanza preloading.

Run inside the API container, where the config and deps match prod:
    docker exec -i zapi python - < tools/memory_baseline_probe.py
"""

import gc
import os
import sys
import time


def rss_mb():
    # /proc exists in the container; fall back to ru_maxrss (peak) on macOS
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except FileNotFoundError:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)


_last = rss_mb()


def step(label):
    global _last
    now = rss_mb()
    print(f"{now:8.0f} MB  (+{now - _last:6.0f})  {label}", flush=True)
    _last = now


def timed_import(label, statement):
    t = time.time()
    exec(statement, globals())
    step(f"{label}  [{time.time() - t:.1f}s]")


os.environ["PRELOAD_STANZA"] = "false"
step("bare interpreter")

timed_import("flask + sqlalchemy", "import flask, sqlalchemy, flask_sqlalchemy")
timed_import("zeeguu.core.model", "import zeeguu.core.model")


timed_import("zeeguu.api.endpoints (all blueprints)", "import zeeguu.api.endpoints")

import wordstats

# create_app preloads with LanguageInfo.load(code) per language; stub both
# entry points so this stays wordstats-free if the preload changes shape again
wordstats.LanguageInfo.load = staticmethod(lambda *a, **k: {})
wordstats.LanguageInfo.load_in_memory_for = staticmethod(lambda *a, **k: None)
timed_import("create_app() (wordstats + stanza preload stubbed)",
             "from zeeguu.api.app import create_app; app = create_app()")

gc.collect()
step("after gc.collect()")

# Which top-level packages got imported, and how many modules each
print("\n--- heaviest top-level packages by module count ---")
counts = {}
for name in list(sys.modules):
    top = name.split(".")[0]
    counts[top] = counts.get(top, 0) + 1
for top, n in sorted(counts.items(), key=lambda kv: -kv[1])[:25]:
    print(f"{n:6d}  {top}")

# Python object census: what the GC-tracked heap is made of
print("\n--- top GC-tracked object types ---")
types = {}
for o in gc.get_objects():
    t = type(o).__name__
    types[t] = types.get(t, 0) + 1
for t, n in sorted(types.items(), key=lambda kv: -kv[1])[:20]:
    print(f"{n:10d}  {t}")

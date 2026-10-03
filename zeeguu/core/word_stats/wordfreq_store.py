"""
wordfreq's word frequencies, read from a SQLite file per language instead of
from memory.

wordfreq.zipf_frequency loads a language's whole list into a dict and keeps it
for the life of the process: 30-80 MB per language (measured 2026-10-04: looking
up one word in each of 19 languages took a process from 30 MB to 718 MB). In
the API that is every gunicorn worker. So, as wordstats does with its own lists
(see wordstats/disk_store.py), each list is built once into a read-only SQLite
file and read through mmap: the pages live in the OS page cache, shared by all
processes, and each process keeps one connection.

zipf_frequency() here answers exactly as wordfreq.zipf_frequency(word, lang)
does: same language matching, tokenizer, token combination and rounding. Only
where the frequency dict lives has changed.
"""

import fcntl
import glob
import hashlib
import math
import os
import sqlite3
import tempfile
import threading
from functools import lru_cache

import langcodes
from wordfreq import available_languages, cB_to_freq, freq_to_zipf, read_cBpack
from wordfreq.language_info import get_language_info
from wordfreq.numbers import digit_freq, smash_numbers
from wordfreq.tokens import lossy_tokenize

# bump when the schema or the way rows are derived from the lists changes
FORMAT_VERSION = 1
MMAP_SIZE = 256 * 1024 * 1024
# wordfreq.zipf_frequency multiplies by this per word break it had to infer (Chinese)
INFERRED_SPACE_FACTOR = 10.0


@lru_cache(maxsize=None)
def _source_file(lang: str) -> str:
    """The wordlist wordfreq would use for `lang` (its 'best' list, closest language match)."""
    available = available_languages("best")
    best, _distance = langcodes.closest_match(lang, list(available), max_distance=60)
    if best == "und":
        raise LookupError(f"No wordfreq list for language {lang!r}")
    return available[best]


def _cache_folder() -> str:
    folder = os.environ.get("WORDFREQ_CACHE_DIR")
    if not folder:
        folder = os.path.join(os.path.dirname(_source_file("en")), "sqlite")
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            folder = None
        if folder and not os.access(folder, os.W_OK):
            folder = None
        if not folder:
            folder = os.path.join(tempfile.gettempdir(), "wordfreq")
    os.makedirs(folder, exist_ok=True)
    return folder


def _store_path(source_file: str) -> str:
    digest = hashlib.sha1(f"{FORMAT_VERSION}|".encode())
    with open(source_file, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    list_name = os.path.basename(source_file).split(".")[0]  # e.g. large_da
    return os.path.join(_cache_folder(), f"{list_name}-{digest.hexdigest()[:12]}.sqlite")


def _build(source_file: str, path: str):
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".building")
    os.close(fd)
    try:
        con = sqlite3.connect(tmp_path)
        con.execute("PRAGMA journal_mode=OFF")
        con.execute("PRAGMA synchronous=OFF")
        con.execute("CREATE TABLE words (word TEXT PRIMARY KEY, cb INTEGER NOT NULL) WITHOUT ROWID")
        # bucket i holds the words at -i centibels. A word in two buckets ends up
        # with the later (lower) one, as in wordfreq.get_frequency_dict.
        con.executemany(
            "INSERT OR REPLACE INTO words (word, cb) VALUES (?, ?)",
            ((word, -index) for index, bucket in enumerate(read_cBpack(source_file)) for word in bucket),
        )
        con.commit()
        con.execute("VACUUM")
        con.close()
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _ensure_store(source_file: str) -> str:
    """
    Path of the list's SQLite file, building it first if needed. A lock file
    makes one process build while the others wait; the atomic rename means no one
    opens a half-written file.
    """
    path = _store_path(source_file)
    if os.path.exists(path):
        return path
    with open(path + ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not os.path.exists(path):
            _build(source_file, path)
            prefix = path.rsplit("-", 1)[0]
            for old in glob.glob(f"{prefix}-*.sqlite"):
                if old != path:
                    for leftover in (old, old + ".lock"):
                        try:
                            os.remove(leftover)
                        except OSError:
                            pass
    return path


class _Store:
    """One read-only connection per process and list, shared by its threads."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._con = None
        self._pid = None

    def cb(self, token: str):
        with self._lock:
            # a SQLite connection must never be used across a fork
            if self._pid != os.getpid():
                self._con = sqlite3.connect(
                    f"file:{self.path}?mode=ro&immutable=1", uri=True, check_same_thread=False
                )
                self._con.execute(f"PRAGMA mmap_size={MMAP_SIZE}")
                self._pid = os.getpid()
            row = self._con.execute("SELECT cb FROM words WHERE word = ?", (token,)).fetchone()
        return row[0] if row else None


_stores = {}
_stores_lock = threading.Lock()


def _store(lang: str) -> _Store:
    source_file = _source_file(lang)
    with _stores_lock:
        if source_file not in _stores:
            _stores[source_file] = _Store(_ensure_store(source_file))
        return _stores[source_file]


def zipf_frequency(word: str, lang: str) -> float:
    """
    wordfreq.zipf_frequency(word, lang), from the SQLite file. 0 for a word the
    list doesn't have. Raises LookupError for a language wordfreq doesn't cover.
    """
    store = _store(lang)
    tokens = lossy_tokenize(word, lang)
    if not tokens:
        return 0.0
    # 1 / f = 1 / f1 + 1 / f2 + ... for a word that tokenizes into several
    one_over_result = 0.0
    for token in tokens:
        smashed = smash_numbers(token)
        cb = store.cb(smashed)
        if cb is None:
            return 0.0
        freq = cB_to_freq(cb)
        if smashed != token:
            freq *= digit_freq(token)
        one_over_result += 1.0 / freq
    freq = 1.0 / one_over_result
    if get_language_info(lang)["tokenizer"] == "jieba":
        freq *= INFERRED_SPACE_FACTOR ** -(len(tokens) - 1)
    # wordfreq rounds to 3 significant digits, then to hundredths of a zipf
    leading_zeroes = math.floor(-math.log(freq, 10))
    return round(freq_to_zipf(round(freq, leading_zeroes + 3)), 2)

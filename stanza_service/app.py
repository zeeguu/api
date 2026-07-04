"""
Stanza Tokenization Microservice

A lightweight Flask service that wraps Stanza NLP pipelines for tokenization.
Designed to be run with gunicorn's preload_app=True for memory-efficient
model sharing across workers via copy-on-write.

Endpoints:
- POST /tokenize - Tokenize text into structured tokens
- POST /sentences - Extract sentences from text
- GET /health - Health check
- GET /languages - List supported languages
- GET /stats - Request statistics (for monitoring)
"""

import os
import re
import time
import threading
import psutil
from flask import Flask, request, jsonify
import stanza

# Monitoring - track request stats
_stats_lock = threading.Lock()

# Latency histogram buckets (seconds), Prometheus-style cumulative "le" buckets.
# Boundaries placed from observed data (Grafana), not guesswork: live tokenizes
# cluster in 1-2s and crawl (big-text batches) in 5-15s, so both regions get
# dense resolution. Too-coarse buckets there made histogram_quantile interpolate
# the wide gaps, pinning every percentile to a bucket edge (e.g. p50/p90/p99 all
# stuck at 1.50/1.90/1.99 when everything sat in a single [1,2] bucket).
DURATION_BUCKETS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 15, 20, 30, 60]

_request_stats = {
    "total_requests": 0,
    "slow_requests": 0,  # > 5s
    "errors": 0,
    "total_chars_processed": 0,
    "by_language": {},
    # Duration histogram: cumulative count per "le" bucket, plus sum/count, so
    # Prometheus can derive p50/p90/p99 via histogram_quantile(). The elapsed is
    # already computed per request (see log_request) — we just stop discarding it.
    "duration_sum": 0.0,
    "duration_count": 0,
    "duration_buckets": {b: 0 for b in DURATION_BUCKETS},
}

SLOW_REQUEST_THRESHOLD = 5.0  # seconds

# Configuration
STANZA_RESOURCE_DIR = os.environ.get("STANZA_RESOURCE_DIR", "/stanza_resources")

# Supported languages (must match languages with downloaded models)
SUPPORTED_LANGUAGES = [
    "de", "es", "fr", "nl", "en", "it", "da", "pl", "sv", "ru", "no", "hu", "pt", "ro", "el"
]

# Language code mapping for Stanza compatibility
STANZA_LANG_MAP = {
    'no': 'nb',  # Norwegian -> Norwegian Bokmal
}

# Model types
MODEL_TOKEN_ONLY = "token_only"
MODEL_TOKEN_POS = "token_pos"
MODEL_TOKEN_POS_DEP = "token_pos_dep"  # Default - includes dependency parsing

PROCESSORS_MAP = {
    MODEL_TOKEN_ONLY: "tokenize",
    MODEL_TOKEN_POS: "tokenize,pos",
    MODEL_TOKEN_POS_DEP: "tokenize,pos,lemma,depparse",
}

# Regex patterns
STANZA_PARAGRAPH_DELIMITER = re.compile(r"((\s?)+\\n+)")
PARTICLE_WITH_APOSTROPHE = re.compile(r"(\w+('|'))")

# Punctuation definitions (matching Token class)
from string import punctuation as _std_punctuation
PUNCTUATION = "\u00bb\u00ab" + _std_punctuation + "\u2013\u2014\u201c\u2018\u201d\u201d\u2019\u201e\u00bf\u00bb\u00ab"
LEFT_PUNCTUATION = "({#\u201e\u00bf[\u201c"
RIGHT_PUNCTUATION = ")}\u201d]\u201d"

# Global pipeline cache - loaded once in master, shared via COW after fork
CACHED_PIPELINES = {}
_PIPELINE_LOAD_LOCK = threading.Lock()


def get_stanza_code(lang_code):
    """Map language code to Stanza-compatible code."""
    return STANZA_LANG_MAP.get(lang_code, lang_code)


def get_pipeline(lang_code, model_type):
    """Get or create a Stanza pipeline for the given language and model type."""
    stanza_code = get_stanza_code(lang_code)
    key = (stanza_code, model_type)

    if key not in CACHED_PIPELINES:
        with _PIPELINE_LOAD_LOCK:
            if key not in CACHED_PIPELINES:
                processors = PROCESSORS_MAP.get(model_type, PROCESSORS_MAP[MODEL_TOKEN_POS_DEP])
                print(f"Loading Stanza pipeline: {stanza_code} with {processors}")
                pipeline = stanza.Pipeline(
                    lang=stanza_code,
                    processors=processors,
                    download_method=None,
                    model_dir=STANZA_RESOURCE_DIR,
                )
                CACHED_PIPELINES[key] = pipeline
                print(f"Loaded Stanza pipeline: {stanza_code}")

    return CACHED_PIPELINES[key]


def preload_all_models():
    """Preload all language models. Called before forking workers."""
    print("Preloading Stanza models for all languages...")
    for lang_code in SUPPORTED_LANGUAGES:
        try:
            get_pipeline(lang_code, MODEL_TOKEN_POS_DEP)
        except Exception as e:
            print(f"Warning: Failed to load model for {lang_code}: {e}")
    print(f"Preloaded {len(CACHED_PIPELINES)} Stanza pipelines")


def tokenize_text(text, lang_code, model_type=MODEL_TOKEN_POS_DEP,
                  flatten=True, start_token_i=0, start_sentence_i=0, start_paragraph_i=0):
    """
    Tokenize text using Stanza.

    Returns a list of token dictionaries with structure matching the Token class.
    """
    pipeline = get_pipeline(lang_code, model_type)
    doc = pipeline(text)

    paragraphs = []
    current_paragraph = []
    s_i = 0

    for sentence in doc.sentences:
        sent_list = []
        is_new_paragraph = False
        accumulator = ""
        t_i = 0

        for i, token in enumerate(sentence.tokens):
            t_details = token.to_dict()[0]
            token_text = t_details["text"]

            # Handle French/Italian particles with apostrophes (l'auteur -> l'auteur)
            particle_match = PARTICLE_WITH_APOSTROPHE.match(token_text)
            has_space = not ("SpaceAfter=No" in t_details.get("misc", ""))

            if (particle_match
                and particle_match.group(0) == token_text
                and i + 1 < len(sentence.tokens)
                and sentence.tokens[i + 1].text not in PUNCTUATION
                and not has_space):
                accumulator += token_text
                continue

            if accumulator:
                token_text = accumulator + token_text
                accumulator = ""

            # Process punctuation (revert tokenizer changes)
            token_text = token_text.replace("``", '"').replace("''", '"')

            # Build token dictionary
            token_dict = {
                "text": token_text,
                "par_i": len(paragraphs) + start_paragraph_i,
                "sent_i": s_i + start_sentence_i,
                "token_i": t_i + start_token_i,
                "has_space": has_space,
                "pos": t_details.get("upos"),
                "dep": t_details.get("deprel"),
                "head": t_details.get("head"),
                "lemma": t_details.get("lemma"),
                # Computed fields (matching Token class behavior)
                "is_sent_start": t_i == 0,
                "is_punct": token_text in PUNCTUATION or token_text in ("...", "…"),
                "is_left_punct": token_text in LEFT_PUNCTUATION,
                "is_right_punct": token_text in RIGHT_PUNCTUATION,
            }

            sent_list.append(token_dict)
            t_i += 1

            if STANZA_PARAGRAPH_DELIMITER.search(t_details.get("misc", "")):
                is_new_paragraph = True

        current_paragraph.append(sent_list)
        s_i += 1

        if is_new_paragraph:
            paragraphs.append(current_paragraph)
            current_paragraph = []
            s_i = 0

    paragraphs.append(current_paragraph)

    if flatten:
        # Flatten: paragraphs > sentences > tokens -> flat list of tokens
        return [token for para in paragraphs for sent in para for token in sent]

    return paragraphs


def get_sentences(text, lang_code, model_type=MODEL_TOKEN_POS_DEP):
    """Extract sentences from text."""
    pipeline = get_pipeline(lang_code, model_type)
    doc = pipeline(text)
    return [" ".join([token.text for token in sent.tokens]) for sent in doc.sentences]


# Flask application
app = Flask(__name__)


def log_request(endpoint, language, chars, elapsed, is_error=False):
    """Track request statistics for monitoring."""
    with _stats_lock:
        _request_stats["total_requests"] += 1
        _request_stats["total_chars_processed"] += chars

        # Latency histogram (all requests, success or error). Cumulative "le"
        # buckets: bump every bucket whose upper bound the request fits under.
        _request_stats["duration_sum"] += elapsed
        _request_stats["duration_count"] += 1
        for b in DURATION_BUCKETS:
            if elapsed <= b:
                _request_stats["duration_buckets"][b] += 1

        if is_error:
            _request_stats["errors"] += 1
        elif elapsed > SLOW_REQUEST_THRESHOLD:
            _request_stats["slow_requests"] += 1
            print(f"STANZA-SLOW: {endpoint} took {elapsed:.1f}s for {chars} chars ({language})")

        # Track by language
        if language not in _request_stats["by_language"]:
            _request_stats["by_language"][language] = {"requests": 0, "chars": 0, "slow": 0}
        _request_stats["by_language"][language]["requests"] += 1
        _request_stats["by_language"][language]["chars"] += chars
        if elapsed > SLOW_REQUEST_THRESHOLD:
            _request_stats["by_language"][language]["slow"] += 1


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint with memory info."""
    process = psutil.Process()
    mem_info = process.memory_info()
    return jsonify({
        "status": "ok",
        "pipelines_loaded": len(CACHED_PIPELINES),
        "memory_mb": round(mem_info.rss / 1024 / 1024, 1),
        "memory_percent": round(process.memory_percent(), 1),
    })


@app.route("/stats", methods=["GET"])
def stats():
    """Request statistics for monitoring Stanza health."""
    process = psutil.Process()
    mem_info = process.memory_info()
    with _stats_lock:
        return jsonify({
            "requests": _request_stats.copy(),
            "memory_mb": round(mem_info.rss / 1024 / 1024, 1),
            "memory_percent": round(process.memory_percent(), 1),
            "pipelines_loaded": len(CACHED_PIPELINES),
            "languages_loaded": list(set(k[0] for k in CACHED_PIPELINES.keys())),
        })


@app.route("/languages", methods=["GET"])
def languages():
    """List supported languages."""
    return jsonify({
        "languages": SUPPORTED_LANGUAGES,
        "loaded": list(set(k[0] for k in CACHED_PIPELINES.keys()))
    })


@app.route("/tokenize", methods=["POST"])
def tokenize_endpoint():
    """
    Tokenize text.

    Request JSON:
        {
            "text": "Text to tokenize",
            "language": "en",
            "model": "token_pos_dep",  // optional, default: token_pos_dep
            "flatten": true,           // optional, default: true
            "start_token_i": 0,        // optional
            "start_sentence_i": 0,     // optional
            "start_paragraph_i": 0     // optional
        }

    Response JSON:
        {
            "tokens": [...]
        }
    """
    start_time = time.time()
    data = request.get_json()

    if not data:
        return jsonify({"error": "JSON body required"}), 400

    text = data.get("text", "")
    language = data.get("language")
    model = data.get("model", MODEL_TOKEN_POS_DEP)
    flatten = data.get("flatten", True)
    start_token_i = data.get("start_token_i", 0)
    start_sentence_i = data.get("start_sentence_i", 0)
    start_paragraph_i = data.get("start_paragraph_i", 0)

    if not language:
        return jsonify({"error": "language is required"}), 400

    if language not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"Unsupported language: {language}"}), 400

    if not text:
        return jsonify({"tokens": []})

    try:
        tokens = tokenize_text(
            text, language, model, flatten,
            start_token_i, start_sentence_i, start_paragraph_i
        )
        elapsed = time.time() - start_time
        log_request("tokenize", language, len(text), elapsed)
        return jsonify({"tokens": tokens})
    except Exception as e:
        elapsed = time.time() - start_time
        log_request("tokenize", language, len(text), elapsed, is_error=True)
        print(f"STANZA-ERROR: tokenize failed for {language} ({len(text)} chars): {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/tokenize_batch", methods=["POST"])
def tokenize_batch_endpoint():
    """
    Tokenize multiple texts in a single request.

    This is much more efficient than calling /tokenize multiple times
    because all texts are processed in sequence without HTTP overhead.

    Request JSON:
        {
            "texts": ["Text 1", "Text 2", ...],
            "language": "da",
            "model": "token_pos_dep",  // optional
            "flatten": false           // optional, default: false for batch
        }

    Response JSON:
        {
            "results": [
                {"tokens": [...]},
                {"tokens": [...]},
                ...
            ]
        }
    """
    start_time = time.time()
    data = request.get_json()

    if not data:
        return jsonify({"error": "JSON body required"}), 400

    texts = data.get("texts", [])
    language = data.get("language")
    model = data.get("model", MODEL_TOKEN_POS_DEP)
    flatten = data.get("flatten", False)

    if not language:
        return jsonify({"error": "language is required"}), 400

    if language not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"Unsupported language: {language}"}), 400

    if not texts:
        return jsonify({"results": []})

    total_chars = sum(len(t) for t in texts if t)

    try:
        results = []
        for text in texts:
            if not text:
                results.append({"tokens": []})
            else:
                tokens = tokenize_text(text, language, model, flatten)
                results.append({"tokens": tokens})
        elapsed = time.time() - start_time
        log_request("tokenize_batch", language, total_chars, elapsed)
        if elapsed > SLOW_REQUEST_THRESHOLD:
            print(f"STANZA-SLOW: tokenize_batch took {elapsed:.1f}s for {len(texts)} texts, {total_chars} chars ({language})")
        return jsonify({"results": results})
    except Exception as e:
        elapsed = time.time() - start_time
        log_request("tokenize_batch", language, total_chars, elapsed, is_error=True)
        print(f"STANZA-ERROR: tokenize_batch failed for {language} ({len(texts)} texts): {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/metrics", methods=["GET"])
def prometheus_metrics():
    """Prometheus-format metrics for scraping."""
    process = psutil.Process()
    mem_info = process.memory_info()

    lines = [
        "# HELP stanza_requests_total Total number of tokenization requests",
        "# TYPE stanza_requests_total counter",
        f"stanza_requests_total {_request_stats['total_requests']}",
        "",
        "# HELP stanza_slow_requests_total Requests taking longer than 5 seconds",
        "# TYPE stanza_slow_requests_total counter",
        f"stanza_slow_requests_total {_request_stats['slow_requests']}",
        "",
        "# HELP stanza_errors_total Total number of failed requests",
        "# TYPE stanza_errors_total counter",
        f"stanza_errors_total {_request_stats['errors']}",
        "",
        "# HELP stanza_chars_processed_total Total characters processed",
        "# TYPE stanza_chars_processed_total counter",
        f"stanza_chars_processed_total {_request_stats['total_chars_processed']}",
        "",
        "# HELP stanza_memory_bytes Memory usage in bytes",
        "# TYPE stanza_memory_bytes gauge",
        f"stanza_memory_bytes {mem_info.rss}",
        "",
        "# HELP stanza_pipelines_loaded Number of loaded language pipelines",
        "# TYPE stanza_pipelines_loaded gauge",
        f"stanza_pipelines_loaded {len(CACHED_PIPELINES)}",
    ]

    # Latency histogram + per-language metrics
    worker = os.getpid()
    with _stats_lock:
        # Tokenize-duration histogram, labelled per worker: each gunicorn worker
        # keeps its own in-memory counters (preload_app is off), so a bare series
        # would sawtooth as scrapes land on different workers. The pid label keeps
        # each series monotonic; sum across workers in PromQL, e.g.
        #   histogram_quantile(0.9, sum by (le) (rate(stanza_tokenize_duration_seconds_bucket[5m])))
        lines.extend([
            "",
            "# HELP stanza_tokenize_duration_seconds Tokenization request duration in seconds",
            "# TYPE stanza_tokenize_duration_seconds histogram",
        ])
        for b in DURATION_BUCKETS:
            lines.append(
                f'stanza_tokenize_duration_seconds_bucket{{worker="{worker}",le="{b}"}} '
                f'{_request_stats["duration_buckets"][b]}'
            )
        lines.append(
            f'stanza_tokenize_duration_seconds_bucket{{worker="{worker}",le="+Inf"}} '
            f'{_request_stats["duration_count"]}'
        )
        lines.append(
            f'stanza_tokenize_duration_seconds_sum{{worker="{worker}"}} {_request_stats["duration_sum"]}'
        )
        lines.append(
            f'stanza_tokenize_duration_seconds_count{{worker="{worker}"}} {_request_stats["duration_count"]}'
        )

        # Per-language metrics
        if _request_stats["by_language"]:
            lines.extend([
                "",
                "# HELP stanza_requests_by_language Requests per language",
                "# TYPE stanza_requests_by_language counter",
            ])
            for lang, stats in _request_stats["by_language"].items():
                lines.append(f'stanza_requests_by_language{{language="{lang}"}} {stats["requests"]}')

            lines.extend([
                "",
                "# HELP stanza_slow_by_language Slow requests per language",
                "# TYPE stanza_slow_by_language counter",
            ])
            for lang, stats in _request_stats["by_language"].items():
                lines.append(f'stanza_slow_by_language{{language="{lang}"}} {stats["slow"]}')

    return "\n".join(lines) + "\n", 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/sentences", methods=["POST"])
def sentences_endpoint():
    """
    Extract sentences from text.

    Request JSON:
        {
            "text": "Text with multiple sentences.",
            "language": "en"
        }

    Response JSON:
        {
            "sentences": ["Text with multiple sentences."]
        }
    """
    start_time = time.time()
    data = request.get_json()

    if not data:
        return jsonify({"error": "JSON body required"}), 400

    text = data.get("text", "")
    language = data.get("language")
    model = data.get("model", MODEL_TOKEN_POS_DEP)

    if not language:
        return jsonify({"error": "language is required"}), 400

    if language not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"Unsupported language: {language}"}), 400

    if not text:
        return jsonify({"sentences": []})

    try:
        sentences = get_sentences(text, language, model)
        elapsed = time.time() - start_time
        log_request("sentences", language, len(text), elapsed)
        return jsonify({"sentences": sentences})
    except Exception as e:
        elapsed = time.time() - start_time
        log_request("sentences", language, len(text), elapsed, is_error=True)
        print(f"STANZA-ERROR: sentences failed for {language} ({len(text)} chars): {e}")
        return jsonify({"error": str(e)}), 500


# NOTE: Models are loaded lazily on first request per language
# preload_all_models() is NOT called at import time because:
# - With preload_app=True: PyTorch hangs after fork
# - With preload_app=False: Each worker loads on demand (more reliable)


if __name__ == "__main__":
    # For development only - preload then run
    preload_all_models()
    app.run(host="0.0.0.0", port=5001, debug=True)

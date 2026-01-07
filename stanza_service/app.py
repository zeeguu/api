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
"""

import os
import re
import threading
from flask import Flask, request, jsonify
import stanza

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


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "pipelines_loaded": len(CACHED_PIPELINES)})


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
        return jsonify({"tokens": tokens})
    except Exception as e:
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

    try:
        results = []
        for text in texts:
            if not text:
                results.append({"tokens": []})
            else:
                tokens = tokenize_text(text, language, model, flatten)
                results.append({"tokens": tokens})
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
        return jsonify({"sentences": sentences})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# NOTE: Models are loaded lazily on first request per language
# preload_all_models() is NOT called at import time because:
# - With preload_app=True: PyTorch hangs after fork
# - With preload_app=False: Each worker loads on demand (more reliable)


if __name__ == "__main__":
    # For development only - preload then run
    preload_all_models()
    app.run(host="0.0.0.0", port=5001, debug=True)

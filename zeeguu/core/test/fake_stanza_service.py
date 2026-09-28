"""
Stand-in for the Stanza service in tests.

The API never runs Stanza in-process, and tests should not need the real
service (torch, models, gigabytes of RAM). requests_mock answers the service's
endpoints here with the in-process NLTK tokenizer, in the same response shape,
so code under test still gets realistic paragraphs/sentences/tokens. What it
does not reproduce is Stanza's own output (POS, lemmas, dependencies, its
exact splits); that belongs to stanza_service's own behaviour.
"""

import json
import re

import requests_mock


def _tokenizer(payload):
    from zeeguu.core.model.language import Language
    from zeeguu.core.tokenization.nltk_tokenizer import NLTKTokenizer

    return NLTKTokenizer(Language.find(payload["language"]))


def _tokenize(request, context):
    p = json.loads(request.text)
    tokens = _tokenizer(p).tokenize_text(
        p["text"],
        True,
        p.get("flatten", True),
        p.get("start_token_i", 0),
        p.get("start_sentence_i", 0),
        p.get("start_paragraph_i", 0),
    )
    return {"tokens": tokens}


def _tokenize_batch(request, context):
    p = json.loads(request.text)
    tokenizer = _tokenizer(p)
    flatten = p.get("flatten", False)
    return {"results": [{"tokens": tokenizer.tokenize_text(t, True, flatten)} for t in p["texts"]]}


def _sentences(request, context):
    p = json.loads(request.text)
    return {"sentences": _tokenizer(p).get_sentences(p["text"])}


def register_fake_stanza_service(m, base_url):
    base = re.escape(base_url.rstrip("/"))
    m.post(re.compile(f"^{base}/tokenize$"), json=_tokenize)
    m.post(re.compile(f"^{base}/tokenize_batch$"), json=_tokenize_batch)
    m.post(re.compile(f"^{base}/sentences$"), json=_sentences)

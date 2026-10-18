# Length caps on free text that ends up in a paid LLM, MT or TTS call.
#
# The per-day rate limits (rate_limiter.py) bound how many calls one account
# makes; these bound how big each call can be. Without them a single request
# can carry an arbitrarily long "word" or "context" into a prompt, and the
# token bill grows with it.
#
# Each cap sits well above anything a client legitimately sends, so that a 400
# from here means a hand-crafted request, never a learner with a long sentence.
import flask

from zeeguu.api.utils.abort_handling import make_error

# A word or phrase a learner taps, selects or types. Idioms and multi-word
# expressions are a few dozen characters; a selected clause, a few hundred.
MAX_PHRASE_CHARS = 1000

# The sentence around a translated word. Readers send one sentence, with
# ellipses; 10k covers even the run-on, punctuation-free "sentences" that some
# scraped pages produce.
MAX_CONTEXT_CHARS = 10_000

# A whole text that a teacher adapts in the editor. Simplification output is
# capped at 8000 tokens (simplification_service.LEVEL_MAX_TOKENS), so a text
# much past ~40k characters already comes back truncated as a 422; 60k leaves
# room for scripts that pack more characters into a token.
MAX_OWN_TEXT_CHARS = 60_000

# An article translated and adapted in one LLM call. The reply is capped at
# 16000 tokens, about 60k characters; anything much longer than that cannot
# come back whole, so we refuse it before paying for the input tokens.
MAX_ARTICLE_CHARS_FOR_LLM = 100_000

# Titles, URLs, a typed cloze answer: short by nature.
MAX_TITLE_CHARS = 1000
MAX_URL_CHARS = 2048


def abort_if_too_long(name, value, max_chars):
    """
    400 with a JSON {message} when `value` is longer than `max_chars`.

    Refuse rather than truncate: a truncated word or context would be
    translated, cached and stored under a key that no longer matches what the
    client sent.
    """
    if value is not None and len(value) > max_chars:
        flask.abort(make_error(400, f"{name} is too long (maximum {max_chars} characters)"))

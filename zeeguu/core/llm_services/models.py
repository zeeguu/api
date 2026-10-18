"""
Central registry of every LLM model Zeeguu talks to.

Single source of truth: this is the only place raw model-ID strings should
live. Call sites import a *role* constant (e.g. ``WORD_TRANSLATION``) instead of
hardcoding a dated snapshot. When a provider retires a snapshot, we change one
line here instead of grepping the whole codebase.

This exists because of a concrete outage: ``claude-sonnet-4-20250514`` was
hardcoded in the reader's translation path, Anthropic stopped serving that
snapshot (404 ``not_found_error``), and the "Ask LLM" action silently failed
("Ask LLM — try again") with no single place to fix it. Grouping by role rather
than by vendor keeps "what model runs where" readable at a glance and makes
re-pointing a feature to a cheaper/faster tier a one-line edit.

Model IDs are authoritative as of 2026-10 (Sonnet 4.5 retires 2026-11-30). See
https://platform.claude.com/docs/en/about-claude/models/overview for current IDs.
"""

from zeeguu.logging import log

# --- Canonical model IDs — the ONLY place a raw model string appears ---
ANTHROPIC_SONNET = "claude-sonnet-5-5"  # current Sonnet tier; thinking off via claude.request_options
ANTHROPIC_HAIKU = "claude-haiku-5-5"  # current Haiku (fast / cheap); low-effort thinking via claude.request_options
DEEPSEEK_CHAT = "deepseek-chat"

# --- The most a model writes in one reply. ---
# A request above it is rejected outright: deepseek-chat answers max_tokens >
# 8192 with HTTP 400 "Invalid max_tokens". So no call site knows these numbers;
# each asks for what its reply needs through output_tokens(), and a model with a
# lower cap -- typically the fallback -- gets its cap instead of a 400. On
# 2026-10-18 the A0 audio lessons asked for 16000, which would have failed every
# time Anthropic did.
# Keys are model-id prefixes, matched like claude.py matches its models, so a
# new snapshot of a listed family is capped too. A model matching none is not
# capped here.
# DeepSeek: https://api-docs.deepseek.com/quick_start/pricing
MAX_OUTPUT_TOKENS = {
    "deepseek-": 8192,
}


def output_tokens(model: str, wanted: int) -> int:
    """max_tokens to send `model` for a reply that may need `wanted` tokens.

    Capped at what the model accepts. A reply that needs more than the cap comes
    back cut off, and most paths still return it as complete (zeeguu/api#863).
    Every capping is logged, so the callers that ask a model for more than it
    writes show up in the logs rather than passing silently."""
    cap = next(
        (cap for prefix, cap in MAX_OUTPUT_TOKENS.items() if model.startswith(prefix)),
        None,
    )
    if cap is not None and wanted > cap:
        log(f"max_tokens capped for {model}: asked {wanted}, sent {cap}")
        return cap
    return wanted

# --- Roles → model. Change the right-hand side to re-point a feature. ---

# Reader "Ask LLM" on-demand single word/phrase translation (ADR 022) and
# separated-MWE translation. Both are gated behind a user click, so a cheaper
# tier (ANTHROPIC_HAIKU) would be a reasonable cost cut; kept on Sonnet to
# preserve the behaviour these paths had before the outage.
WORD_TRANSLATION = ANTHROPIC_SONNET
MWE_TRANSLATION = ANTHROPIC_SONNET

# Multi-word-expression detection during article tokenization.
MWE_DETECTION = ANTHROPIC_SONNET

# Translation validation / provider-agreement checks before exercises.
TRANSLATION_VALIDATION = ANTHROPIC_SONNET

# Judging whether another word a learner typed into a cloze also fits
# ("tænker" where the exercise expected "synes"). A learner is waiting, but
# each verdict is stored and shared by all learners, so accuracy on nuance
# (register, idiomaticity) is worth the slower tier.
CLOZE_ALTERNATIVE_JUDGE = ANTHROPIC_SONNET

# Judging whether another translation a learner typed is also right
# ("consult" where the exercise expected "look up" for "slå op"). Same
# reasoning as the cloze judge: shared verdicts, worth the slower tier.
TRANSLATION_ALTERNATIVE_JUDGE = ANTHROPIC_SONNET

# Meaning-frequency classification (COMMON / RARE / …). NOTE: also used as the
# DB lookup key in AiGenerator.get_current_classification_model — keep the model
# a classification run records and the model looked up in sync via this one constant.
MEANING_FREQUENCY = ANTHROPIC_SONNET

# General-purpose Anthropic SDK service (background example / text generation).
ANTHROPIC_GENERAL = ANTHROPIC_SONNET

# Explaining a selected word in its sentence. DeepSeek first, Anthropic behind
# it -- the reverse of the usual order here, and measured rather than assumed.
# On the Danish compound that breaks models -- narrøv, which is nar + røv and
# which every model tested has at some point rendered as nar + "øv (donkey)" --
# measured six runs each at temperature 0:
#
#   DeepSeek  6/6 correct, 1.17s average
#   Sonnet    5/6 correct, 2.71s average
#   Haiku     0/3 correct on every prompt variant tried
#
# So this is not only the faster provider but the more reliable one on the case
# that matters, and it is also the more accurate on register: it calls the word
# vulgar where Sonnet softens it to "mildly vulgar".
WORD_EXPLANATION = DEEPSEEK_CHAT
WORD_EXPLANATION_FALLBACK = ANTHROPIC_SONNET

# Article simplification + CEFR classification (real-time Haiku key path).
SIMPLIFICATION = ANTHROPIC_HAIKU

# Grammar / spelling correction of simplified text (provider-selectable).
GRAMMAR_CORRECTION_ANTHROPIC = ANTHROPIC_HAIKU
GRAMMAR_CORRECTION_DEEPSEEK = DEEPSEEK_CHAT

# DeepSeek general chat (simplification + its fallback path).
DEEPSEEK_GENERAL = DEEPSEEK_CHAT

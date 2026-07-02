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

Model IDs are authoritative as of 2026-07. See
https://platform.claude.com/docs/en/about-claude/models/overview for current IDs.
"""

# --- Canonical model IDs — the ONLY place a raw model string appears ---
ANTHROPIC_SONNET = "claude-sonnet-4-5-20250929"  # current Sonnet tier
ANTHROPIC_HAIKU = "claude-haiku-4-5-20251001"    # current Haiku (fast / cheap)
DEEPSEEK_CHAT = "deepseek-chat"

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

# Meaning-frequency classification (COMMON / RARE / …). NOTE: also used as the
# DB lookup key in AiGenerator.get_current_classification_model — keep the model
# a classification run records and the model looked up in sync via this one constant.
MEANING_FREQUENCY = ANTHROPIC_SONNET

# General-purpose Anthropic SDK service (background example / text generation).
ANTHROPIC_GENERAL = ANTHROPIC_SONNET

# Article simplification + CEFR classification (real-time Haiku key path).
SIMPLIFICATION = ANTHROPIC_HAIKU

# Grammar / spelling correction of simplified text (provider-selectable).
GRAMMAR_CORRECTION_ANTHROPIC = ANTHROPIC_HAIKU
GRAMMAR_CORRECTION_DEEPSEEK = DEEPSEEK_CHAT

# DeepSeek general chat (simplification + its fallback path).
DEEPSEEK_GENERAL = DEEPSEEK_CHAT

#!/usr/bin/env python
"""
Offline comparison of Haiku models on Zeeguu's Haiku tasks, on stored articles.

Runs the SAME production prompts, through the SAME production call + parse code,
on the SAME stored articles, once per model variant, and writes a comparison
report. Nothing is written to the database: the script only calls the functions
that build the prompt, call the model and parse the reply, never the ones that
save the result (see "Read-only" below).

Variants
    A  claude-haiku-4-5-20251001, exactly as production calls it today
       (same max_tokens, same temperature via claude.sampling_options).
    B  claude-haiku-5-5, thinking off ({"type": "disabled"}), default effort.
    C  claude-haiku-5-5, adaptive thinking at effort "low" (only with --with-c).
       Thinking tokens count toward max_tokens, so C gets the production
       max_tokens plus --c-thinking-headroom; without it the 30-token CEFR call
       would be cut off every time.

Tasks (--tasks, default all three)
    assess      Crawl-time assessment: simplification_and_classification
                .assess_and_summarize (CEFR, summaries, article type, the
                incomplete / advertorial rejection with REJECTION_STOPS, the
                disturbing flag, and the production language-retry).
    cefr_topic  SimplificationService._assess_cefr_anthropic (CEFR + topic,
                max_tokens 30).
    grammar     GrammarCorrectionService._correct_with_anthropic + its parser,
                on stored simplified versions (children of an article).

Sample
    --n recent original articles (default 200), stratified by language with
    extra weight on German and Danish (--lang-weights), plus a share
    (--junk-fraction) of articles prod already rejected through the LLM:
    article_broken_code_map.broken_code in (LLM_PAYWALL, ADVERTORIAL_LLM).
    Note: prod labels come from whichever provider assessed the article at crawl
    time (DeepSeek and Haiku 4.5 alternate), so they are a reference, not truth.
    Articles under 100 words are skipped, as the crawler does.
    "Recent" means among the last --recent article ids (a primary-key range, so
    it does not scan the article table). --article-ids replaces the sampling.
    The ids used are saved in sample.json; pass them back with --article-ids
    to rerun on the same set.

Cost
    Before anything is generated, the exact prompts of a few sampled items per
    task are measured with the API's count_tokens (free) for each model, and the
    estimated cost of the whole run is printed. The run needs --yes (or an
    interactive "y") to go on. --max-cost aborts mid-run once the cost of what
    has actually been generated (from usage) passes it.

Output (in --out-dir, default $ZEEGUU_DATA_FOLDER/haiku_eval/<timestamp>)
    rows.jsonl   one row per (article, task, variant): raw output, parsed
                 fields, parse ok, stop reasons, truncated, refused, tokens,
                 latency, cost, every underlying call
    rows.csv     the same rows, flat
    summary.md   the comparison report
    sample.json  the article ids used

Usage
    python -m tools.eval_haiku_models --n 200 --yes
    python -m tools.eval_haiku_models --n 200 --with-c --yes
    python -m tools.eval_haiku_models --article-ids 123,456 --tasks assess
    python -m tools.eval_haiku_models --estimate-only --n 200
    python -m tools.eval_haiku_models --report-only /zeeguu-data/haiku_eval/<ts>

Read-only
    The DB session refuses to flush (before_flush raises) and every new MySQL
    connection is put in READ ONLY transaction mode. The functions called do no
    DB work: assess_and_summarize (not assess_summarize_and_classify, which
    commits), _assess_cefr_anthropic, _correct_with_anthropic and the parsers.
"""

import argparse
import csv
import json
import os
import random
import statistics
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic

HAIKU_45 = "claude-haiku-4-5-20251001"
HAIKU_55 = "claude-haiku-5-5"

# $ per million tokens (input, output). Haiku 5.5 has a second rate card
# ($0.50/$2.50) above 100K prompt tokens; no prompt here comes near that.
PRICES = {HAIKU_45: (1.00, 5.00), HAIKU_55: (0.10, 0.50)}

VARIANTS = {
    "A": {"model": HAIKU_45, "label": "Haiku 4.5 (current)"},
    "B": {"model": HAIKU_55, "label": "Haiku 5.5, thinking off"},
    "C": {"model": HAIKU_55, "label": "Haiku 5.5, adaptive thinking, effort low"},
}

TASKS = ["assess", "cefr_topic", "grammar"]
CEFR = ["A1", "A2", "B1", "B2", "C1", "C2"]
TOPICS = [
    "Sports", "Culture & Art", "Technology & Science", "Travel & Tourism",
    "Health & Society", "Business", "Politics", "Satire",
]
LLM_JUNK_CODES = ("LLM_PAYWALL", "ADVERTORIAL_LLM")

# Rough output sizes for the pre-run estimate only (input is measured exactly).
EST_OUTPUT_TOKENS = {"assess": 600, "cefr_topic": 12}
EST_GRAMMAR_OUTPUT_SHARE = 0.5  # corrected text ~ half the prompt's tokens
EST_C_THINKING_TOKENS = {"assess": 300, "cefr_topic": 150, "grammar": 300}
TOKENIZER_GROWTH_55 = 1.3  # Haiku 5.5 counts the same text as ~30% more tokens


def cost(model, input_tokens, output_tokens):
    pin, pout = PRICES[model]
    return (input_tokens * pin + output_tokens * pout) / 1_000_000


# ---------------------------------------------------------------------------
# The model switch: one replacement for haiku_client._create, per-thread state
# ---------------------------------------------------------------------------

_tls = threading.local()


class _CountOnly(Exception):
    """Raised instead of generating when we only want the prompt's token count."""


def _install_model_switch(c_thinking_headroom):
    """
    Replace haiku_client._create (what every Haiku call goes through since #833)
    with a version that sends the current thread's variant and records every
    call. Callers keep parsing the response exactly as in production.
    """
    from zeeguu.core.llm_services import claude, haiku_client

    def _create(prompt, max_tokens, temperature, timeout, stop_sequences=None):
        variant = _tls.variant
        model = VARIANTS[variant]["model"]
        api_key = os.environ["ANTHROPIC_TEXT_SIMPLIFICATION_KEY"]
        # Retries, unlike production: a 429/529 here would be scored as the
        # model failing, which is not what we are measuring.
        client = anthropic.Anthropic(api_key=api_key, timeout=max(timeout, 120), max_retries=3)
        messages = [{"role": "user", "content": prompt}]

        if getattr(_tls, "count_only", False):
            n = client.messages.count_tokens(model=model, messages=messages).input_tokens
            _tls.counted.append(n)
            raise _CountOnly(n)

        kwargs = dict(claude.request_options(model))
        kwargs.update(claude.sampling_options(model, temperature))
        if variant == "B":
            kwargs["thinking"] = {"type": "disabled"}
        elif variant == "C":
            kwargs["thinking"] = {"type": "adaptive"}
            kwargs["output_config"] = {"effort": "low"}
            max_tokens = max_tokens + c_thinking_headroom
        if stop_sequences:
            kwargs["stop_sequences"] = stop_sequences

        call = {"model": model, "max_tokens": max_tokens}
        start = time.time()
        try:
            response = client.messages.create(
                model=model, max_tokens=max_tokens, messages=messages, **kwargs
            )
        except Exception as e:
            call.update(latency_s=time.time() - start, error=f"{type(e).__name__}: {e}")
            _tls.calls.append(call)
            raise
        call.update(
            latency_s=time.time() - start,
            stop_reason=response.stop_reason,
            stop_sequence=response.stop_sequence,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            text=claude.response_text(response),
            thinking_blocks=sum(1 for b in response.content if b.type == "thinking"),
        )
        _tls.calls.append(call)
        return response

    haiku_client._create = _create


# ---------------------------------------------------------------------------
# Tasks: each returns the parsed fields; the raw calls are in _tls.calls
# ---------------------------------------------------------------------------


def _run_assess(item):
    from zeeguu.core.llm_services import simplification_and_classification as sac

    out = {"outcome": "ok"}
    try:
        result = sac.assess_and_summarize(
            item["title"], item["content"], item["lang"], simplification_provider="anthropic"
        )
    except _CountOnly:
        raise
    except Exception as e:
        msg = str(e)
        if msg.startswith("PAYWALL"):
            out["outcome"] = "rejected_incomplete"
        elif msg.startswith("ADVERTORIAL"):
            out["outcome"] = "rejected_advertorial"
        else:
            out["outcome"] = "error"
            out["error"] = f"{type(e).__name__}: {msg}"
        result = None

    calls_ok = [c for c in _tls.calls if "text" in c]
    if result is None and calls_ok:
        # Rejected: read the fields off the last reply ourselves.
        result = sac._parse_assessment_and_summary(calls_ok[-1]["text"], "anthropic", "")
    if result is None:
        return out

    rejected = out["outcome"].startswith("rejected")
    out.update(
        cefr=result.get("original_cefr_level") or None,
        article_type=result.get("article_type"),
        is_incomplete=bool(result.get("is_incomplete")) or out["outcome"] == "rejected_incomplete",
        is_advertorial=bool(result.get("is_advertorial")) or out["outcome"] == "rejected_advertorial",
        # A stop sequence ends the reply before DISTURBING_CONTENT is written.
        is_disturbing=None if rejected else bool(result.get("is_disturbing")),
        summary=result.get("original_summary") or "",
        level_summaries=result.get("level_summaries", {}),
        level_titles=result.get("level_titles", {}),
        language_retry=len(_tls.calls) > 1,
    )
    if not rejected:
        # What production would have dropped: the last reply had a summary but
        # the returned one is empty -> the language check removed it.
        parsed_last = sac._parse_assessment_and_summary(calls_ok[-1]["text"], "anthropic", "") if calls_ok else {}
        out["summary_dropped_for_language"] = bool(parsed_last.get("original_summary")) and not out["summary"]
    out["parse_ok"] = rejected or (
        out["cefr"] in CEFR and out["article_type"] in ("news", "general") and bool(
            out["summary"] or out.get("summary_dropped_for_language")
        )
    )
    if out["summary"]:
        from zeeguu.core.language.language_check import language_mismatch

        out["summary_words"] = len(out["summary"].split())
        out["summary_wrong_language"] = language_mismatch(out["summary"], item["lang"], "summary") is not None
    return out


def _run_cefr_topic(item):
    from zeeguu.core.llm_services.simplification_service import SimplificationService

    result = SimplificationService()._assess_cefr_anthropic(item["title"], item["content"], item["lang"])
    if not result:
        return {"parse_ok": False, "cefr": None, "topic": None}
    cefr_level, topic = result
    return {"parse_ok": cefr_level in CEFR and topic in TOPICS, "cefr": cefr_level, "topic": topic}


def _run_grammar(item):
    from zeeguu.core.language.language_check import field_mismatches
    from zeeguu.core.llm_services.grammar_correction_service import GrammarCorrectionService
    from zeeguu.core.llm_services.prompts.grammar_correction import get_full_article_correction_prompt

    service = GrammarCorrectionService()
    original = {"title": item["title"], "content": item["content"], "summary": item["summary"]}
    prompt = get_full_article_correction_prompt(item["lang"]).format(**original)
    text = service._correct_with_anthropic(prompt)
    corrected = service._parse_correction_response(text, original)
    mismatches = field_mismatches([(f, corrected.get(f, "")) for f in original], item["lang"])
    labels_found = all(f"{label}:" in text for label in ("TITLE", "CONTENT", "SUMMARY"))
    return {
        "parse_ok": labels_found,
        "corrected": corrected,
        "wrong_language": bool(mismatches),
        "content_change_ratio": round(1 - SequenceMatcher(None, item["content"], corrected["content"]).ratio(), 4),
    }


TASK_FNS = {"assess": _run_assess, "cefr_topic": _run_cefr_topic, "grammar": _run_grammar}


def run_one(task, variant, item):
    _tls.variant = variant
    _tls.calls = []
    _tls.count_only = False
    start = time.time()
    try:
        parsed = TASK_FNS[task](item)
    except Exception as e:
        parsed = {"parse_ok": False, "outcome": "error", "error": f"{type(e).__name__}: {e}"}
    wall = time.time() - start
    calls = _tls.calls
    model = VARIANTS[variant]["model"]
    tin = sum(c.get("input_tokens", 0) for c in calls)
    tout = sum(c.get("output_tokens", 0) for c in calls)
    stops = [c.get("stop_reason") for c in calls]
    return {
        "article_id": item["id"],
        "lang": item["lang"],
        "task": task,
        "variant": variant,
        "model": model,
        "parse_ok": bool(parsed.get("parse_ok")),
        "truncated": "max_tokens" in stops,
        "refused": "refusal" in stops,
        "stop_reasons": stops,
        "n_calls": len(calls),
        "input_tokens": tin,
        "output_tokens": tout,
        "cost_usd": cost(model, tin, tout),
        "latency_s": sum(c.get("latency_s", 0) for c in calls),
        "wall_s": wall,
        "raw_output": calls[-1].get("text") if calls else None,
        "parsed": parsed,
        "calls": calls,
        "prod": item.get("prod", {}),
    }


def count_prompt_tokens(task, variant, item):
    """Exact input tokens of the first prompt this task would send."""
    _tls.variant = variant
    _tls.calls = []
    _tls.count_only = True
    _tls.counted = []
    try:
        TASK_FNS[task](item)
    except _CountOnly:
        pass
    except Exception as e:
        print(f"  (could not count tokens for {task}/{item['id']}: {e})")
    finally:
        _tls.count_only = False
    return _tls.counted[0] if _tls.counted else None


# ---------------------------------------------------------------------------
# Sampling (read-only)
# ---------------------------------------------------------------------------


def _q(sql, **params):
    from sqlalchemy import text
    from zeeguu.core.model.db import db

    return db.session.execute(text(sql), params).fetchall()


def sample_ids(n, recent, junk_recent, junk_fraction, lang_weights, n_grammar, seed):
    rng = random.Random(seed)
    max_id = _q("SELECT MAX(id) FROM article")[0][0]

    junk_rows = _q(
        "SELECT a.id, l.code FROM article_broken_code_map m "
        "JOIN article a ON a.id = m.article_id JOIN language l ON l.id = a.language_id "
        f"WHERE m.broken_code IN ({', '.join(repr(c) for c in LLM_JUNK_CODES)}) "
        "AND a.id > :min_id AND a.parent_article_id IS NULL",
        min_id=max_id - junk_recent,
    )
    n_junk = min(len(junk_rows), round(n * junk_fraction))
    junk = [r[0] for r in rng.sample(list(junk_rows), n_junk)]

    rows = _q(
        "SELECT a.id, l.code FROM article a JOIN language l ON l.id = a.language_id "
        "WHERE a.id > :min_id AND a.parent_article_id IS NULL AND a.broken = 0 "
        "AND a.cefr_level IS NOT NULL",
        min_id=max_id - recent,
    )
    by_lang = defaultdict(list)
    for aid, code in rows:
        by_lang[code].append(aid)
    for ids in by_lang.values():
        rng.shuffle(ids)
    # Quota per language by weight, largest remainder so the quotas sum to n.
    weights = {lang: lang_weights.get(lang, 1.0) for lang in by_lang}
    total_w = sum(weights.values()) or 1
    n_clean = n - n_junk
    exact = {lang: n_clean * w / total_w for lang, w in weights.items()}
    quotas = {lang: int(x) for lang, x in exact.items()}
    for lang in sorted(exact, key=lambda l: exact[l] - quotas[l], reverse=True)[: n_clean - sum(quotas.values())]:
        quotas[lang] += 1

    grammar = []
    if n_grammar:
        child_rows = _q(
            "SELECT a.id FROM article a WHERE a.id > :min_id AND a.parent_article_id IS NOT NULL "
            "AND a.broken = 0",
            min_id=max_id - recent * 5,
        )
        ids = [r[0] for r in child_rows]
        grammar = rng.sample(ids, min(len(ids), 2 * n_grammar))
    return junk, dict(by_lang), quotas, grammar


def load_item(article_id, with_prod=True):
    """
    The article as plain data, through raw SELECTs (not the ORM: no session
    state to flush, and no dependency on every mapped column existing).
    Content is the stored text, the same thing Article.get_content() returns.
    """
    found = _q(
        "SELECT a.id, l.code, a.title, a.summary, a.parent_article_id, a.cefr_level, "
        "a.article_type, COALESCE(st.content, a.content) "
        "FROM article a JOIN language l ON l.id = a.language_id "
        "LEFT JOIN source s ON s.id = a.source_id "
        "LEFT JOIN source_text st ON st.id = s.source_text_id "
        "WHERE a.id = :i",
        i=article_id,
    )
    if not found:
        return None
    aid, lang, title, summary, parent_id, cefr_level, article_type, content = found[0]
    content = content or ""
    # The crawler skips assessing articles under 100 words.
    if len(content.split()) < 100:
        return None
    item = {
        "id": aid,
        "lang": lang,
        "title": title or "",
        "content": content,
        "summary": summary or "",
        "is_child": parent_id is not None,
    }
    if with_prod:
        codes = [r[0] for r in _q("SELECT broken_code FROM article_broken_code_map WHERE article_id = :i", i=aid)]
        disturbing = _q(
            "SELECT 1 FROM article_classification WHERE article_id = :i "
            "AND classification_type = 'DISTURBING' AND detection_method = 'LLM'", i=aid,
        )
        generator = _q(
            "SELECT g.model_name FROM level_adapted_article_text t "
            "JOIN ai_generator g ON g.id = t.ai_generator_id WHERE t.article_id = :i LIMIT 1", i=aid,
        )
        item["prod"] = {
            "cefr": cefr_level,
            "article_type": article_type,
            "broken_codes": codes,
            "rejected": any(c in LLM_JUNK_CODES for c in codes),
            "disturbing_llm": bool(disturbing),
            "assessed_by": generator[0][0] if generator else None,
        }
    return item


def make_db_read_only():
    from sqlalchemy import event
    from zeeguu.core.model.db import db

    @event.listens_for(db.session, "before_flush")
    def _refuse(session, flush_context, instances):
        raise RuntimeError("eval_haiku_models is read-only: refusing to flush")

    engine = db.engine
    if engine.dialect.name == "mysql":
        @event.listens_for(engine, "connect")
        def _read_only(dbapi_conn, record):
            cur = dbapi_conn.cursor()
            cur.execute("SET SESSION TRANSACTION READ ONLY")
            cur.close()

        db.session.remove()
        engine.dispose()  # pooled connections predate the listener


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "n/a"


def _quantile(values, q):
    values = sorted(values)
    if not values:
        return None
    return values[min(len(values) - 1, int(q * len(values)))]


def _cefr_diff(a, b):
    if a in CEFR and b in CEFR:
        return abs(CEFR.index(a) - CEFR.index(b))
    return None


def _confusion(pairs, title, rows_label="A", cols_label="other"):
    """pairs: list of (row value, column value), booleans or None."""
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    c = Counter(pairs)
    n = len(pairs)
    agree = c[(True, True)] + c[(False, False)]
    return [
        f"**{title}** — agreement {_pct(agree, n)} (n={n})",
        "",
        f"| | {cols_label} YES | {cols_label} NO |",
        "|---|---|---|",
        f"| {rows_label} YES | {c[(True, True)]} | {c[(True, False)]} |",
        f"| {rows_label} NO | {c[(False, True)]} | {c[(False, False)]} |",
        "",
    ]


def write_report(rows, out_dir, meta):
    by = defaultdict(dict)  # (task, article_id) -> variant -> row
    for r in rows:
        by[(r["task"], r["article_id"])][r["variant"]] = r
    variants = sorted({r["variant"] for r in rows})
    tasks = [t for t in TASKS if any(r["task"] == t for r in rows)]
    others = [v for v in variants if v != "A"]
    L = [f"# Haiku model comparison — {meta.get('started', '')}", ""]
    L += [f"- {v}: {VARIANTS[v]['label']} (`{VARIANTS[v]['model']}`)" for v in variants]
    L += ["- B sends `thinking: {type: disabled}` at the default effort (medium); C sends adaptive "
          "thinking at effort low, with max_tokens raised by "
          f"{meta.get('args', {}).get('c_thinking_headroom')} because thinking counts toward it."]
    L += [f"- Articles: {meta.get('n_articles')} (prod-rejected junk: {meta.get('n_junk')}); "
          f"grammar items: {meta.get('n_grammar')}", ""]
    L += ["CEFR, topic and junk labels have no ground truth here: agreement is measured against "
          "A (today's behaviour). Prod labels came from DeepSeek or Haiku 4.5 (round-robin at crawl time).", ""]

    # Health per task/variant
    L += ["## Parse failures, truncation, refusals, latency, cost", "",
          "| task | variant | rows | parse fail | truncated | refused | errors | median s | p95 s | $ / 1000 items |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for t in tasks:
        for v in variants:
            rs = [r for r in rows if r["task"] == t and r["variant"] == v]
            if not rs:
                continue
            lat = [r["latency_s"] for r in rs if r["n_calls"]]
            errors = sum(1 for r in rs if r["parsed"].get("outcome") == "error" or not r["n_calls"])
            per_item = sum(r["cost_usd"] for r in rs) / len(rs)
            med = statistics.median(lat) if lat else 0
            p95 = _quantile(lat, 0.95) or 0
            L.append(
                f"| {t} | {v} | {len(rs)} | {_pct(sum(not r['parse_ok'] for r in rs), len(rs))} | "
                f"{_pct(sum(r['truncated'] for r in rs), len(rs))} | {sum(r['refused'] for r in rs)} | "
                f"{errors} | {med:.2f} | {p95:.2f} | ${1000 * per_item:.2f} |"
            )
    L += ["", "Cost uses the token counts the API reported, at list prices "
          f"({', '.join(f'{m}: ${p[0]}/${p[1]} per M' for m, p in PRICES.items())}).", ""]

    examples = []

    if "assess" in tasks:
        L += ["## Crawl-time assessment (assess_and_summarize)", ""]
        for v in others:
            pairs = [(d["A"], d[v]) for (t, _), d in by.items() if t == "assess" and "A" in d and v in d]
            pa = lambda p, k: (p[0]["parsed"].get(k), p[1]["parsed"].get(k))
            rej = lambda r: (r["parsed"].get("outcome", "").startswith("rejected")
                             if r["parsed"].get("outcome") != "error" else None)
            L += [f"### A vs {v}", ""]
            L += _confusion([(rej(a), rej(b)) for a, b in pairs], "Rejected (incomplete or advertorial)", "A", v)
            L += _confusion([pa(p, "is_incomplete") for p in pairs], "INCOMPLETE_ARTICLE", "A", v)
            L += _confusion([pa(p, "is_advertorial") for p in pairs], "ADVERTORIAL_CONTENT", "A", v)
            L += _confusion([pa(p, "is_disturbing") for p in pairs],
                            "DISTURBING_CONTENT (only where neither rejected)", "A", v)
            L += _confusion([(p[0]["prod"].get("rejected"), rej(p[1])) for p in pairs if p[0]["prod"]],
                            f"Rejected at crawl time in prod vs rejected by {v}", "prod", v)
            L += _confusion([(p[0]["prod"].get("rejected"), rej(p[0])) for p in pairs if p[0]["prod"]],
                            "Rejected at crawl time in prod vs rejected by A today", "prod", "A")

            diffs = [(_cefr_diff(*pa(p, "cefr")), p) for p in pairs]
            diffs = [(d, p) for d, p in diffs if d is not None]
            n = len(diffs)
            L += [f"**CEFR vs A** (n={n}): exact {_pct(sum(d == 0 for d, _ in diffs), n)}, "
                  f"off by one {_pct(sum(d == 1 for d, _ in diffs), n)}, "
                  f"off by more {_pct(sum(d > 1 for d, _ in diffs), n)}", ""]
            for name, k in (("A", 0), (v, 1)):
                dist = Counter(p[k]["parsed"].get("cefr") for _, p in diffs)
                L.append(f"- {name} distribution: " + ", ".join(f"{c}: {dist.get(c, 0)}" for c in CEFR))
            L.append("")
            types = [pa(p, "article_type") for p in pairs if all(pa(p, "article_type"))]
            L += [f"**Article type vs A**: {_pct(sum(a == b for a, b in types), len(types))} (n={len(types)})", ""]

            dis = [(d, p) for d, p in diffs if d > 0]
            if dis:
                L += [f"CEFR disagreements to look at (A → {v}, prod):", "",
                      "| article | lang | A | " + v + " | prod | title |", "|---|---|---|---|---|---|"]
                for d, p in sorted(dis, key=lambda x: -x[0]):
                    a, b = p
                    L.append(f"| {a['article_id']} | {a['lang']} | {a['parsed'].get('cefr')} | "
                             f"{b['parsed'].get('cefr')} | {a['prod'].get('cefr')} | "
                             f"{(a.get('title') or '')[:60]} |")
                L.append("")

            for a, b in pairs:
                if rej(a) != rej(b) or any(a["parsed"].get(k) != b["parsed"].get(k)
                                           for k in ("is_incomplete", "is_advertorial", "is_disturbing")):
                    examples.append((0, "assess", v, a, b))
                elif (_cefr_diff(a["parsed"].get("cefr"), b["parsed"].get("cefr")) or 0) > 1:
                    examples.append((1, "assess", v, a, b))
                elif (_cefr_diff(a["parsed"].get("cefr"), b["parsed"].get("cefr")) or 0) == 1:
                    examples.append((3, "assess", v, a, b))

        L += ["### Summaries", "",
              "Prompt cap for ORIGINAL_SUMMARY is ~70 words (the 25-word cap belongs to level "
              "simplification, which is not evaluated here).", "",
              "| variant | with summary | median words | p95 words | ≤25 words | ≤70 words | wrong language (final) | language retry | dropped for language |",
              "|---|---|---|---|---|---|---|---|---|"]
        for v in variants:
            rs = [r for r in rows if r["task"] == "assess" and r["variant"] == v
                  and not r["parsed"].get("outcome", "").startswith("rejected")]
            words = [r["parsed"]["summary_words"] for r in rs if r["parsed"].get("summary_words")]
            L.append(
                f"| {v} | {len(words)}/{len(rs)} | {statistics.median(words) if words else '-'} | "
                f"{_quantile(words, 0.95) or '-'} | {_pct(sum(w <= 25 for w in words), len(words))} | "
                f"{_pct(sum(w <= 70 for w in words), len(words))} | "
                f"{sum(bool(r['parsed'].get('summary_wrong_language')) for r in rs)} | "
                f"{sum(bool(r['parsed'].get('language_retry')) for r in rs)} | "
                f"{sum(bool(r['parsed'].get('summary_dropped_for_language')) for r in rs)} |"
            )
        L.append("")

    if "cefr_topic" in tasks:
        L += ["## CEFR + topic (SimplificationService._assess_cefr_anthropic)", ""]
        for v in others:
            pairs = [(d["A"], d[v]) for (t, _), d in by.items() if t == "cefr_topic" and "A" in d and v in d]
            diffs = [_cefr_diff(a["parsed"].get("cefr"), b["parsed"].get("cefr")) for a, b in pairs]
            diffs = [d for d in diffs if d is not None]
            n = len(diffs)
            topics = [(a["parsed"].get("topic"), b["parsed"].get("topic")) for a, b in pairs
                      if a["parsed"].get("topic") and b["parsed"].get("topic")]
            L += [f"### A vs {v}", "",
                  f"- CEFR (n={n}): exact {_pct(diffs.count(0), n)}, off by one {_pct(diffs.count(1), n)}, "
                  f"off by more {_pct(sum(d > 1 for d in diffs), n)}",
                  f"- Topic agreement: {_pct(sum(a == b for a, b in topics), len(topics))} (n={len(topics)})", ""]
            confused = Counter((a, b) for a, b in topics if a != b)
            if confused:
                L += ["Most common topic disagreements (A → " + v + "): " +
                      "; ".join(f"{a} → {b} ×{k}" for (a, b), k in confused.most_common(6)), ""]
            dis = [(a, b) for a, b in pairs
                   if (_cefr_diff(a["parsed"].get("cefr"), b["parsed"].get("cefr")) or 0) > 0]
            if dis:
                L += ["| article | lang | A | " + v + " | prod | A topic | " + v + " topic |",
                      "|---|---|---|---|---|---|---|"]
                for a, b in dis:
                    L.append(f"| {a['article_id']} | {a['lang']} | {a['parsed'].get('cefr')} | "
                             f"{b['parsed'].get('cefr')} | {a['prod'].get('cefr')} | "
                             f"{a['parsed'].get('topic')} | {b['parsed'].get('topic')} |")
                L.append("")
            for a, b in pairs:
                if a["parsed"].get("topic") != b["parsed"].get("topic"):
                    examples.append((2, "cefr_topic", v, a, b))

    if "grammar" in tasks:
        L += ["## Grammar correction (Anthropic provider)", "",
              "| variant | rows | labels parsed | wrong language | median content change | p95 content change |",
              "|---|---|---|---|---|---|"]
        for v in variants:
            rs = [r for r in rows if r["task"] == "grammar" and r["variant"] == v]
            ch = [r["parsed"]["content_change_ratio"] for r in rs if "content_change_ratio" in r["parsed"]]
            L.append(f"| {v} | {len(rs)} | {_pct(sum(r['parse_ok'] for r in rs), len(rs))} | "
                     f"{sum(bool(r['parsed'].get('wrong_language')) for r in rs)} | "
                     f"{statistics.median(ch) if ch else '-'} | {_quantile(ch, 0.95) if ch else '-'} |")
        L.append("")
        for v in others:
            pairs = [(d["A"], d[v]) for (t, _), d in by.items() if t == "grammar" and "A" in d and v in d]
            sims = [SequenceMatcher(None, a["parsed"]["corrected"]["content"], b["parsed"]["corrected"]["content"]).ratio()
                    for a, b in pairs if "corrected" in a["parsed"] and "corrected" in b["parsed"]]
            if sims:
                L += [f"- A vs {v}: corrected-content similarity median {statistics.median(sims):.3f}, "
                      f"min {min(sims):.3f} (n={len(sims)})", ""]

    # Side-by-side examples
    examples.sort(key=lambda e: e[0])
    L += ["## Disagreement examples", ""]
    if not examples:
        L += ["None.", ""]
    for _, task, v, a, b in examples[:15]:
        L += [f"### {task} — article {a['article_id']} ({a['lang']}) — A vs {v}", "",
              f"Title: {a.get('title', '')}", f"Prod: {json.dumps(a['prod'], ensure_ascii=False)}", ""]
        for name, r in (("A", a), (v, b)):
            p = {k: r["parsed"].get(k) for k in ("outcome", "cefr", "topic", "article_type", "is_incomplete",
                                                  "is_advertorial", "is_disturbing", "summary") if k in r["parsed"]}
            L += [f"**{name}**: `{json.dumps(p, ensure_ascii=False)}`", ""]
        L.append("")

    path = os.path.join(out_dir, "summary.md")
    with open(path, "w") as f:
        f.write("\n".join(L))
    return path


def write_rows(rows, out_dir):
    with open(os.path.join(out_dir, "rows.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    fields = ["article_id", "lang", "task", "variant", "model", "parse_ok", "truncated", "refused",
              "stop_reasons", "n_calls", "input_tokens", "output_tokens", "cost_usd", "latency_s",
              "outcome", "cefr", "topic", "article_type", "is_incomplete", "is_advertorial",
              "is_disturbing", "summary_words", "summary_wrong_language", "prod_cefr", "prod_rejected",
              "error", "raw_output"]
    with open(os.path.join(out_dir, "rows.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            flat = {**r, **{k: v for k, v in r["parsed"].items() if k in fields}}
            flat["stop_reasons"] = ",".join(str(s) for s in r["stop_reasons"])
            flat["prod_cefr"] = r["prod"].get("cefr")
            flat["prod_rejected"] = r["prod"].get("rejected")
            w.writerow(flat)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def estimate(work, variants, sample_per_task):
    """Exact input tokens of a few prompts per task (count_tokens), extrapolated."""
    total = 0.0
    per_task_variant = {}
    print("\nEstimating cost from count_tokens on the exact prompts:")
    for task in TASKS:
        items = [it for t, it in work if t == task]
        if not items:
            continue
        probe = items[:sample_per_task]
        for v in variants:
            counts = [count_prompt_tokens(task, v, it) for it in probe]
            counts = [c for c in counts if c]
            if not counts:
                continue
            tin = statistics.mean(counts)
            model = VARIANTS[v]["model"]
            if task == "grammar":
                tout = tin * EST_GRAMMAR_OUTPUT_SHARE
            else:
                tout = EST_OUTPUT_TOKENS[task] * (TOKENIZER_GROWTH_55 if model == HAIKU_55 else 1)
            if v == "C":
                tout += EST_C_THINKING_TOKENS[task]
            each = cost(model, tin, tout)
            per_task_variant[(task, v)] = each
            total += each * len(items)
            print(f"  {task:10s} {v}: ~{tin:,.0f} in / ~{tout:,.0f} out tokens per item "
                  f"→ ${each:.4f}/item, ${1000 * each:.2f}/1000, ${each * len(items):.2f} for {len(items)}")
    print(f"  Estimated total for this run: ${total:.2f} (output sizes are rough guesses; input is measured)")
    return total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=200, help="articles for assess + cefr_topic")
    ap.add_argument("--n-grammar", type=int, default=20, help="simplified versions for grammar")
    ap.add_argument("--article-ids", help="comma-separated article ids instead of sampling")
    ap.add_argument("--grammar-ids", help="comma-separated simplified-article ids for grammar")
    ap.add_argument("--tasks", default=",".join(TASKS))
    ap.add_argument("--with-c", action="store_true", help="add variant C (5.5, adaptive thinking, low effort)")
    ap.add_argument("--c-thinking-headroom", type=int, default=2048)
    ap.add_argument("--junk-fraction", type=float, default=0.15)
    ap.add_argument("--lang-weights", default="de:3,da:2", help="sampling weight per language (others 1)")
    ap.add_argument("--recent", type=int, default=20000, help="sample among the last N article ids")
    ap.add_argument("--junk-recent", type=int, default=200000, help="look for prod-rejected junk among the last N ids")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-cost", type=float, default=25.0, help="abort once this many USD are spent")
    ap.add_argument("--estimate-sample", type=int, default=3, help="prompts per task measured for the estimate")
    ap.add_argument("--estimate-only", action="store_true")
    ap.add_argument("--yes", action="store_true", help="run without asking after the estimate")
    ap.add_argument("--out-dir")
    ap.add_argument("--report-only", metavar="DIR", help="rebuild summary.md from DIR/rows.jsonl")
    args = ap.parse_args()

    if args.report_only:
        with open(os.path.join(args.report_only, "rows.jsonl")) as f:
            rows = [json.loads(line) for line in f]
        meta = json.load(open(os.path.join(args.report_only, "sample.json"))).get("meta", {})
        print(write_report(rows, args.report_only, meta))
        return

    if not os.environ.get("ANTHROPIC_TEXT_SIMPLIFICATION_KEY"):
        sys.exit("ANTHROPIC_TEXT_SIMPLIFICATION_KEY is not set")

    from zeeguu.api.app import create_app_for_scripts

    app = create_app_for_scripts()
    app.app_context().push()
    make_db_read_only()

    import zeeguu
    print(f"zeeguu imported from {zeeguu.__file__}")
    from zeeguu.core.llm_services import haiku_client
    if not hasattr(haiku_client, "_create"):
        sys.exit("haiku_client has no _create: this needs the SDK client from zeeguu/api#833")
    _install_model_switch(args.c_thinking_headroom)

    tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]
    variants = ["A", "B"] + (["C"] if args.with_c else [])
    lang_weights = {k: float(v) for k, v in (p.split(":") for p in args.lang_weights.split(",") if p)}

    # --- sample ---
    n_junk = 0
    gram_ids = []
    if args.article_ids:
        junk = []
        by_lang = {None: [int(x) for x in args.article_ids.split(",") if x.strip()]}
        quotas = {None: len(by_lang[None])}
    else:
        junk, by_lang, quotas, gram_ids = sample_ids(
            args.n, args.recent, args.junk_recent, args.junk_fraction, lang_weights,
            args.n_grammar if "grammar" in tasks else 0, args.seed,
        )
    articles = []
    for aid in junk:
        it = load_item(aid)
        if it:
            articles.append(it)
            n_junk += 1

    def take(lang, k):
        taken = 0
        while taken < k and by_lang[lang]:
            it = load_item(by_lang[lang].pop(0))
            if it and not it["is_child"]:
                articles.append(it)
                taken += 1
        return taken

    # Fill each language's quota; whatever a language is short of (too few
    # recent articles over 100 words) goes to the others, in turn.
    shortfall = sum(k - take(lang, k) for lang, k in quotas.items())
    while shortfall > 0 and any(by_lang.values()):
        for lang in by_lang:
            if shortfall > 0 and take(lang, 1):
                shortfall -= 1

    grammar_items = []
    if "grammar" in tasks:
        if args.grammar_ids:
            gram_ids = [int(x) for x in args.grammar_ids.split(",") if x.strip()]
        for aid in gram_ids:
            if len(grammar_items) >= args.n_grammar:
                break
            it = load_item(aid, with_prod=False)
            if it and it["is_child"]:
                it["prod"] = {}
                grammar_items.append(it)

    from zeeguu.core.model.db import db
    db.session.rollback()  # nothing to roll back; just release the connection

    print(f"\nSample: {len(articles)} articles ({n_junk} prod-rejected junk), "
          f"{len(grammar_items)} grammar items")
    print("  by language: " + ", ".join(f"{k}: {v}" for k, v in Counter(a["lang"] for a in articles).most_common()))

    work = [(t, it) for t in tasks if t != "grammar" for it in articles]
    work += [("grammar", it) for it in grammar_items]
    if not work:
        sys.exit("Nothing to do: the sample is empty.")

    est = estimate(work, variants, args.estimate_sample)
    if args.estimate_only:
        return
    if est > args.max_cost:
        print(f"  Note: estimate exceeds --max-cost ${args.max_cost:.2f}; the run will stop there.")
    if not args.yes:
        if not sys.stdin.isatty():
            sys.exit("Not a terminal: pass --yes to run.")
        if input("Run? [y/N] ").strip().lower() != "y":
            sys.exit("Aborted.")

    started = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_dir = args.out_dir or os.path.join(
        os.environ.get("ZEEGUU_DATA_FOLDER") or ".", "haiku_eval", started
    )
    os.makedirs(out_dir, exist_ok=True)
    meta = {"started": started, "n_articles": len(articles), "n_junk": n_junk,
            "n_grammar": len(grammar_items), "variants": variants, "tasks": tasks, "args": vars(args)}
    with open(os.path.join(out_dir, "sample.json"), "w") as f:
        json.dump({"article_ids": [a["id"] for a in articles],
                   "grammar_ids": [g["id"] for g in grammar_items], "meta": meta}, f, indent=1)

    titles = {it["id"]: it["title"] for it in articles + grammar_items}
    jobs = [(t, v, it) for t, it in work for v in variants]
    rows, spent, stop = [], 0.0, threading.Event()

    def guarded(t, v, it):
        if stop.is_set():
            return None
        return run_one(t, v, it)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(guarded, *j) for j in jobs]
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            if r is None:
                continue
            r["title"] = titles.get(r["article_id"], "")
            rows.append(r)
            spent += r["cost_usd"]
            if i % 20 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} done, ${spent:.2f} spent")
            if spent > args.max_cost and not stop.is_set():
                print(f"  --max-cost ${args.max_cost:.2f} reached; stopping after in-flight calls")
                stop.set()

    rows.sort(key=lambda r: (r["task"], r["article_id"], r["variant"]))
    write_rows(rows, out_dir)
    report = write_report(rows, out_dir, meta)
    print(f"\nSpent ${spent:.2f}. Wrote {len(rows)} rows to {out_dir}\nReport: {report}")


if __name__ == "__main__":
    main()

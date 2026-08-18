#!/usr/bin/env python
"""
Measure how often the assess+summarize prompt gets the output language right on
the FIRST attempt, for competing prompt variants.

Why this exists: the backfill on 18 Aug 2026 showed the language check failing on
attempt 1 for article after article and passing on attempt 2, which means the
retry — not the prompt — was producing every correct summary, at two LLM calls
and ~5s of extra latency each. 7cd9d6ca had already diagnosed the cause once
("a weak indirection — literal <<LANGUAGE_NAME>> tokens plus a definition at the
very bottom") and fixed only the role line, leaving ten tokens in the field specs.
That is a plausible story. So were several plausible stories today that real data
killed, so this measures instead of assuming.

Costs one LLM call per (article x variant). Read-only: nothing is stored.

    python tools/experiment_summary_prompt_language.py --articles 8
"""

import argparse
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.language.language_check import field_mismatches, describe_mismatches
from zeeguu.core.llm_services.prompts.article_simplification import (
    get_assessment_and_summary_prompt,
)
from zeeguu.core.llm_services.simplification_and_classification import (
    _call_simplification_llm,
    _parse_assessment_and_summary,
    _select_provider_and_key,
    _summaries_to_check,
)
from zeeguu.core.model.article import Article


def as_it_was_before_the_fix(prompt: str, language_name: str) -> str:
    """
    The 929860b6 field specs put back the way they were: the language named once in
    the role line and the CRITICAL directive, but referred to indirectly at each
    field, with the binding at the bottom. This is the baseline to beat.
    """
    body = prompt.replace(f"in {language_name}", "in <<LANGUAGE_NAME>>")
    return body + f"\n\n<<LANGUAGE_NAME>> = {language_name}"


def with_the_rule_repeated_last(prompt: str, language_name: str) -> str:
    """
    Same prompt, with the language rule restated at the very end.

    A long prompt states the rule once, near the top, hundreds of lines before the
    model writes anything. Recency is the cheapest lever there is if that distance
    is what costs us — and if it changes nothing, the distance was not the problem.
    """
    return prompt + (
        f"\n\nBefore you answer, check once more: every summary you are about to "
        f"write must be in {language_name}. Not English. {language_name}."
    )


VARIANTS = {
    "before-fix": as_it_was_before_the_fix,
    "current": lambda prompt, _: prompt,
    "rule-last": with_the_rule_repeated_last,
}


def first_attempt_is_right(article, variant, provider, api_key):
    """One call, no retry — the retry is what we are trying to stop needing."""
    language = article.language.code
    language_name = article.language.name
    prompt = get_assessment_and_summary_prompt(language).format(
        title=article.title, content=article.get_content()
    )
    prompt = VARIANTS[variant](prompt, language_name)

    result, model_name = _call_simplification_llm(
        prompt, provider, api_key, max_tokens=2000, timeout=120
    )
    parsed = _parse_assessment_and_summary(result, provider, model_name)
    mismatches = field_mismatches(_summaries_to_check(parsed), language)
    return (not mismatches), mismatches


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--articles", type=int, default=8, help="articles per variant")
    p.add_argument("--since", default="2026-08-01")
    p.add_argument("--provider", default="anthropic")
    p.add_argument(
        "--variants",
        default=",".join(VARIANTS),
        help=f"comma-separated subset of: {', '.join(VARIANTS)}",
    )
    args = p.parse_args()

    provider, api_key = _select_provider_and_key(args.provider)
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    for v in variants:
        if v not in VARIANTS:
            print(f"Unknown variant: {v}. Known: {', '.join(VARIANTS)}")
            return

    # Non-English articles with real prose. English ones cannot fail the check the
    # way this is measuring, so they would only dilute the rate.
    articles = [
        a
        for a in Article.query.filter(Article.published_time >= args.since)
        .filter(Article.parent_article_id.is_(None))
        .filter(Article.broken == 0)
        .order_by(Article.id.desc())
        .limit(400)
        .all()
        if a.language and a.language.code != "en" and a.get_word_count() >= 200
    ][: args.articles]

    print(f"\n{len(articles)} articles x {len(variants)} variants "
          f"= {len(articles) * len(variants)} calls, provider={provider}\n")

    scores = {v: [0, 0] for v in variants}  # [right, total]
    for article in articles:
        print(f"[{article.id}] {article.language.code} {(article.title or '')[:52]}")
        for variant in variants:
            try:
                ok, mismatches = first_attempt_is_right(
                    article, variant, provider, api_key
                )
            except Exception as e:
                print(f"    {variant:12} ERROR {str(e)[:70]}")
                continue
            scores[variant][1] += 1
            scores[variant][0] += 1 if ok else 0
            detail = "" if ok else f" — {describe_mismatches(mismatches)[:70]}"
            print(f"    {variant:12} {'right' if ok else 'WRONG'}{detail}")

    print("\n=== first-attempt language correct ===")
    for variant in variants:
        right, total = scores[variant]
        if total:
            print(f"  {variant:12} {right}/{total}  {100 * right / total:5.1f}%")


if __name__ == "__main__":
    main()

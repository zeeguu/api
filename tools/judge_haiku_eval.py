#!/usr/bin/env python
"""
Label articles with a stronger model (Claude Opus 5.5): CEFR level, disturbing,
incomplete, advertorial. Blind: the judge never sees what other models said.

Two uses:
1. Settle the disagreements of tools/eval_haiku_models.py runs: every article
   where the variants (Haiku 4.5, Haiku 5.5, DeepSeek, ...) disagree on any of
   the four labels is judged, and the report scores each variant against the
   judge on exactly those articles.
2. Label arbitrary articles (--article-ids), e.g. as training data.

The definitions are cut word for word from the production assessment prompt
(get_assessment_and_summary_prompt), so the judge applies the same rules the
crawler's models are given.

Usage (on the server, inside run_task, like eval_haiku_models):
    python -m tools.judge_haiku_eval --runs /zeeguu-data/haiku_eval/<ts1>,/zeeguu-data/haiku_eval/<ts2> --estimate-only
    python -m tools.judge_haiku_eval --runs ... --yes
    python -m tools.judge_haiku_eval --article-ids 123,456 --yes

Read-only against the DB (same guards as eval_haiku_models). Needs
ANTHROPIC_API_KEY.
"""

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic

from tools.eval_haiku_models import CEFR, load_item, make_db_read_only

JUDGE_MODEL = "claude-opus-5-5"
JUDGE_PRICES = (4.00, 20.00)  # $ per M input / output tokens, claude-opus-5-5 list price
LABELS = ["cefr", "disturbing", "incomplete", "advertorial"]

SCHEMA = {
    "type": "object",
    "properties": {
        "incomplete": {"type": "boolean"},
        "advertorial": {"type": "boolean"},
        "disturbing": {"type": "boolean"},
        "cefr": {"type": "string", "enum": CEFR},
        "reason": {"type": "string"},
    },
    "required": ["incomplete", "advertorial", "disturbing", "cefr", "reason"],
    "additionalProperties": False,
}


def _between(text, start, end):
    i = text.index(start)
    return text[i: text.index(end, i)].strip()


def _field_line(text, field):
    return next(line for line in text.splitlines() if line.startswith(field + ":"))


def judge_prompt(item):
    from zeeguu.core.llm_services.prompts.article_simplification import (
        get_assessment_and_summary_prompt,
    )

    prod = get_assessment_and_summary_prompt(item["lang"])
    rules = "\n\n".join(
        [
            _between(prod, "CEFR Level Guidelines:", "ALWAYS produce"),
            _between(prod, "IMPORTANT: If the article appears to be incomplete", "LEVELS TO SUMMARIZE"),
            _field_line(prod, "INCOMPLETE_ARTICLE"),
            _field_line(prod, "ADVERTORIAL_CONTENT"),
            _field_line(prod, "DISTURBING_CONTENT"),
            _field_line(prod, "ORIGINAL_LEVEL"),
        ]
    )
    return f"""You are labelling a news article for a language-learning app, as an expert language teacher. Apply the rules below exactly as written; they are the rules the app's assessment models are given. Judge the CEFR level of the article's language (vocabulary, grammar, sentence structure), not of its subject.

{rules}

Answer with the four labels and, in "reason", one or two sentences justifying the CEFR level and any YES.

Title: {item["title"]}

Article:
{item["content"]}"""


def judge(client, item, effort):
    t0 = time.time()
    response = client.beta.messages.create(
        model=JUDGE_MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": judge_prompt(item)}],
    )
    usage = response.usage
    row = {
        "article_id": item["id"],
        "lang": item["lang"],
        "title": item["title"],
        "model": response.model,
        "stop_reason": response.stop_reason,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cost_usd": (usage.input_tokens * JUDGE_PRICES[0] + usage.output_tokens * JUDGE_PRICES[1]) / 1e6,
        "latency_s": time.time() - t0,
        "verdict": None,
    }
    if response.stop_reason in ("end_turn", "stop_sequence"):
        text = "".join(b.text for b in response.content if b.type == "text")
        row["verdict"] = json.loads(text)
    return row


# ---------------------------------------------------------------------------
# Disagreements across eval runs
# ---------------------------------------------------------------------------


def variant_labels(row):
    """The four labels from one eval_haiku_models assess row, or None on error."""
    p = row.get("parsed") or {}
    outcome = p.get("outcome", "")
    if outcome == "error" or not row.get("n_calls"):
        return None
    return {
        "incomplete": bool(p.get("is_incomplete")),
        "advertorial": bool(p.get("is_advertorial")),
        # Not assessed once rejected: no opinion, rather than a NO
        "disturbing": p.get("is_disturbing"),
        "cefr": p.get("cefr") if p.get("cefr") in CEFR else None,
    }


def load_runs(run_dirs):
    """{article_id: {variant: labels}}. A variant that appears in several runs
    is keyed by the last run (ordered as given) so each variant counts once;
    earlier copies are kept as '<variant>@<run>' for self-agreement."""
    by_article = defaultdict(dict)
    for run_i, run_dir in enumerate(run_dirs):
        with open(os.path.join(run_dir, "rows.jsonl")) as f:
            for line in f:
                row = json.loads(line)
                if row["task"] != "assess":
                    continue
                labels = variant_labels(row)
                if labels is None:
                    continue
                v = row["variant"]
                if v in by_article[row["article_id"]]:
                    by_article[row["article_id"]][f"{v}@{run_i - 1}"] = by_article[row["article_id"]][v]
                by_article[row["article_id"]][v] = labels
    return by_article


def disagreements(by_article):
    """Article ids where the latest variants disagree on any label."""
    ids = []
    for aid, variants in by_article.items():
        latest = [labels for v, labels in variants.items() if "@" not in v]
        for label in LABELS:
            values = {labels[label] for labels in latest if labels[label] is not None}
            if len(values) > 1:
                ids.append(aid)
                break
    return ids


def write_report(judged, by_article, out_dir):
    variants = sorted({v for vs in by_article.values() for v in vs if "@" not in v})
    L = [f"# Judge ({JUDGE_MODEL}) on eval disagreements", ""]
    ok = [r for r in judged if r["verdict"]]
    L.append(f"Judged {len(judged)} articles; {len(ok)} with a verdict; "
             f"${sum(r['cost_usd'] for r in judged):.2f} spent.")
    L.append("")
    L.append("Each variant scored against the judge, on the articles where the variants disagreed "
             "(where they all agree, they all score the same).")
    L.append("")
    L.append("| variant | rejected (incomplete or advertorial) | disturbing | CEFR exact | CEFR off by one | CEFR off by more |")
    L.append("|---|---|---|---|---|---|")
    for v in variants:
        rej = dist = cefr_n = exact = one = 0
        rej_n = dist_n = 0
        for r in ok:
            labels = by_article.get(r["article_id"], {}).get(v)
            if not labels:
                continue
            j = r["verdict"]
            rej_n += 1
            rej += (labels["incomplete"] or labels["advertorial"]) == (j["incomplete"] or j["advertorial"])
            if labels["disturbing"] is not None and not (j["incomplete"] or j["advertorial"]):
                dist_n += 1
                dist += labels["disturbing"] == j["disturbing"]
            if labels["cefr"]:
                cefr_n += 1
                d = abs(CEFR.index(labels["cefr"]) - CEFR.index(j["cefr"]))
                exact += d == 0
                one += d == 1
        pct = lambda a, b: f"{100 * a / b:.0f}% ({a}/{b})" if b else "–"
        L.append(f"| {v} | {pct(rej, rej_n)} | {pct(dist, dist_n)} | {pct(exact, cefr_n)} | "
                 f"{pct(one, cefr_n)} | {pct(cefr_n - exact - one, cefr_n)} |")
    L.append("")
    L.append("Judge CEFR distribution: " + ", ".join(
        f"{k}: {v}" for k, v in sorted(Counter(r["verdict"]["cefr"] for r in ok).items())))
    L.append("")
    L.append("## Verdicts")
    L.append("")
    L.append("| article | lang | judge | " + " | ".join(variants) + " | reason | title |")
    L.append("|---|---|---|" + "---|" * len(variants) + "---|---|")

    def short(labels):
        if not labels:
            return "–"
        if labels["incomplete"] or labels["advertorial"]:
            return "junk" + (" (inc)" if labels["incomplete"] else " (adv)")
        return f"{labels['cefr'] or '?'}{' D' if labels['disturbing'] else ''}"

    for r in ok:
        j = r["verdict"]
        cells = [short(by_article.get(r["article_id"], {}).get(v)) for v in variants]
        L.append(f"| {r['article_id']} | {r['lang']} | **{short(j)}** | " + " | ".join(cells)
                 + f" | {j['reason'][:160]} | {r['title'][:50]} |")
    L.append("")
    L.append("Cells: CEFR level, `D` = disturbing, `junk (inc|adv)` = rejected as incomplete or advertorial.")
    with open(os.path.join(out_dir, "judge_summary.md"), "w") as f:
        f.write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", help="comma-separated eval_haiku_models output dirs; judge their disagreements")
    ap.add_argument("--article-ids", help="comma-separated article ids to label instead")
    # low: same verdicts as medium on a probe, at the same cost; labelling needs little thinking
    ap.add_argument("--effort", default="low", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--limit", type=int, help="judge at most this many articles")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-cost", type=float, default=30.0, help="stop once this many USD are spent")
    ap.add_argument("--estimate-only", action="store_true", help="judge 3 articles, then extrapolate the cost")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--out-dir")
    args = ap.parse_args()
    if not (args.runs or args.article_ids):
        ap.error("give --runs or --article-ids")

    from zeeguu.api.app import create_app_for_scripts

    app = create_app_for_scripts()
    app.app_context().push()
    make_db_read_only()

    by_article = {}
    if args.runs:
        run_dirs = args.runs.split(",")
        by_article = load_runs(run_dirs)
        ids = disagreements(by_article)
        print(f"{len(by_article)} articles in the runs; variants disagree on {len(ids)}")
    else:
        ids = [int(x) for x in args.article_ids.split(",")]
    if args.limit:
        ids = ids[: args.limit]

    client = anthropic.Anthropic()
    items = []
    for aid in ids:
        item = load_item(aid, with_prod=False)
        if item:
            items.append(item)
    print(f"{len(items)} articles to judge with {JUDGE_MODEL} (effort {args.effort})")

    probe = [judge(client, item, args.effort) for item in items[:3]]
    per_item = sum(r["cost_usd"] for r in probe) / max(len(probe), 1)
    print(f"Measured on {len(probe)}: ${per_item:.3f}/article → about ${per_item * len(items):.2f} for {len(items)}")
    for r in probe:
        print(f"  {r['article_id']} [{r['lang']}] {r['stop_reason']} {r['verdict']}")
    if args.estimate_only:
        return
    if not args.yes:
        print("Re-run with --yes to judge them all.")
        return

    out_dir = args.out_dir or os.path.join(
        os.environ.get("ZEEGUU_DATA_FOLDER", "/zeeguu-data"), "haiku_eval",
        "judge_" + datetime.now().strftime("%Y-%m-%d_%H%M"))
    os.makedirs(out_dir, exist_ok=True)

    judged = list(probe)
    spent = sum(r["cost_usd"] for r in judged)
    with ThreadPoolExecutor(args.workers) as pool:
        futures = {pool.submit(judge, client, item, args.effort): item for item in items[3:]}
        for n, fut in enumerate(as_completed(futures), 1):
            try:
                row = fut.result()
            except Exception as e:  # one failure must not lose the rest of the run
                item = futures[fut]
                row = {"article_id": item["id"], "lang": item["lang"], "title": item["title"],
                       "verdict": None, "error": str(e), "cost_usd": 0.0}
            judged.append(row)
            spent += row["cost_usd"]
            if n % 20 == 0:
                print(f"  {len(judged)}/{len(items)} judged, ${spent:.2f}")
            if spent > args.max_cost:
                print(f"Stopping: spent ${spent:.2f} > --max-cost {args.max_cost}")
                for f in futures:
                    f.cancel()
                break

    with open(os.path.join(out_dir, "judge.jsonl"), "w") as f:
        for r in judged:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if by_article:
        write_report(judged, by_article, out_dir)
    print(f"Spent ${spent:.2f}. Wrote {len(judged)} verdicts to {out_dir}")


if __name__ == "__main__":
    main()

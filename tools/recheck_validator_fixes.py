#!/usr/bin/env python
"""
Re-judge past validator fixes with today's validator. Writes nothing to the
database: the disagreements go to a CSV for review.

A wrong INVALID heals itself (scheduling and the nightly job re-judge anything
not VALID), but a wrong FIX doesn't: the learner moves to a meaning marked
VALID, which is never looked at again ("vil sige" = "mean", 13 Aug 2026).
This asks the current validator about each corrected meaning in the sentence
the fix was made in.

    python -m tools.recheck_validator_fixes --dry-run          # count + cost
    python -m tools.recheck_validator_fixes [--days 30] [--limit 50]
    python -m tools.recheck_validator_fixes --batch-id msgbatch_...   # resume

Every fix that got a verdict is added to --checked (a file of validation_log
ids) and skipped on the next run, so a run of the top 300 now and the rest
next month don't pay twice. Keep that file between runs: in the container,
copy it out with the CSV and back in before the next run.

The first question about each fix goes through the Batch API (half price).
The validator's own retries (a reply that lists options or doesn't fit its
sentence) are asked live afterwards, through the same validate_and_classify
as in production.
"""
import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from sqlalchemy import text

from zeeguu.core.llm_services import claude
from zeeguu.core.llm_services.prompts.translation_validator import (
    VALIDATION_SCHEMA,
    create_combined_validation_prompt,
)
from zeeguu.core.llm_services.translation_validator import TranslationValidator
from zeeguu.core.model.language import Language

# Measured 25 Oct 2026 ("vil sige"): 3,588 tokens in, 299 out
INPUT_TOKENS, OUTPUT_TOKENS = 3600, 300
# Sonnet per million tokens, Batch API (half the list price)
BATCH_INPUT_PRICE, BATCH_OUTPUT_PRICE = 1.5, 7.5

FIXES = """
SELECT MAX(v.id) log_id, MAX(v.created_at) fixed_at, v.new_meaning_id, v.context,
       o.content word, t.content translation, ol.code source, tl.code target,
       (SELECT GROUP_CONCAT(DISTINCT ot.content SEPARATOR ' | ')
          FROM validation_log v2 JOIN meaning om ON om.id = v2.meaning_id
          JOIN phrase ot ON ot.id = om.translation_id
         WHERE v2.action = 'FIXED' AND v2.new_meaning_id = v.new_meaning_id
           AND v2.context = v.context) fixed_from,
       (SELECT COUNT(*) FROM user_word uw
         WHERE uw.meaning_id = v.new_meaning_id
           AND uw.fit_for_study = 1 AND uw.learned_time IS NULL) active_words
FROM validation_log v
JOIN meaning m ON m.id = v.new_meaning_id
JOIN phrase o ON o.id = m.origin_id
JOIN phrase t ON t.id = m.translation_id
JOIN language ol ON ol.id = o.language_id
JOIN language tl ON tl.id = t.language_id
WHERE v.action = 'FIXED' AND v.context IS NOT NULL AND v.context != ''
  AND m.validated = 1
  AND v.created_at > NOW() - INTERVAL :days DAY
GROUP BY v.new_meaning_id, v.context, o.content, t.content, ol.code, tl.code
ORDER BY active_words DESC, log_id
"""


def fixes(days, limit, checked):
    rows = [r for r in db.session.execute(text(FIXES), {"days": days}).mappings().all()
            if r["log_id"] not in checked]
    return rows[:limit] if limit else rows


def read_checked(path):
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        return {int(line) for line in f if line.strip()}


def prompt_for(fix):
    return create_combined_validation_prompt(
        word=fix["word"],
        translation=fix["translation"],
        context=fix["context"],
        source_lang=Language.LANGUAGE_NAMES.get(fix["source"], fix["source"]),
        target_lang=Language.LANGUAGE_NAMES.get(fix["target"], fix["target"]),
    )


def params(prompt):
    return {
        "model": TranslationValidator.MODEL_NAME,
        **claude.request_options(TranslationValidator.MODEL_NAME),
        "max_tokens": 1000,
        "output_config": {"format": {"type": "json_schema", "schema": VALIDATION_SCHEMA}},
        "messages": [{"role": "user", "content": prompt}],
    }


def submit(client, rows):
    batch = client.messages.batches.create(
        requests=[{"custom_id": f"fix-{fix['log_id']}", "params": params(prompt_for(fix))} for fix in rows]
    )
    print(f"Submitted batch {batch.id} ({len(rows)} questions); resume with --batch-id {batch.id}")
    return batch.id


def wait_for(client, batch_id):
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        counts = batch.request_counts
        print(f"  {batch.processing_status}: {counts.succeeded} done, {counts.errored} errored, "
              f"{counts.processing} to go")
        if batch.processing_status == "ended":
            return
        time.sleep(60)


def first_answers(client, batch_id):
    answers = {}
    for entry in client.messages.batches.results(batch_id):
        if entry.result.type == "succeeded":
            try:
                answers[entry.custom_id] = TranslationValidator._parse_response(
                    claude.response_text(entry.result.message).strip()
                )
            except Exception as e:
                print(f"  {entry.custom_id}: unparseable reply ({e})")
    return answers


def judge(live, fix, first):
    """validate_and_classify, with its first question answered by the batch"""
    prompt = prompt_for(fix)

    def ask(asked, schema):
        return first if asked == prompt else live._ask(asked, schema)

    validator = TranslationValidator(ask=ask)
    return validator.validate_and_classify(
        fix["word"], fix["translation"], fix["context"], fix["source"], fix["target"]
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=3650, help="only fixes from the last N days")
    parser.add_argument("--limit", type=int, help="only the N fixes with the most active words")
    parser.add_argument("--batch-id", help="resume: read this batch's answers instead of submitting")
    parser.add_argument("--dry-run", action="store_true", help="count and estimate, ask nothing")
    parser.add_argument("--out", default="validator_fix_recheck.csv")
    parser.add_argument("--checked", default="validator_fix_rechecked.txt",
                        help="ids of fixes already judged: skipped, and this run's are added")
    args = parser.parse_args()

    checked = read_checked(args.checked)
    rows = fixes(args.days, args.limit, checked)
    if checked:
        print(f"Skipping {len(checked)} fixes judged in earlier runs ({args.checked})")
    cost = len(rows) * (INPUT_TOKENS * BATCH_INPUT_PRICE + OUTPUT_TOKENS * BATCH_OUTPUT_PRICE) / 1e6
    print(f"{len(rows)} fixes (meaning + sentence) to re-judge, "
          f"{sum(r['active_words'] for r in rows)} active words on them; about ${cost:.0f} in the batch")
    if args.dry_run:
        return

    live = TranslationValidator()
    batch_id = args.batch_id or submit(live.client, rows)
    wait_for(live.client, batch_id)
    answers = first_answers(live.client, batch_id)

    disagreements = no_verdict = 0
    with open(args.out, "w", newline="") as f, open(args.checked, "a") as judged:
        out = csv.writer(f)
        out.writerow(["log_id", "fixed_at", "meaning_id", "active_words", "word", "fixed_to", "fixed_from",
                      "verdict_now", "card_now", "reason_now", "context"])
        for fix in rows:
            first = answers.get(f"fix-{fix['log_id']}")
            result = judge(live, fix, first) if first else None
            if result is None:
                no_verdict += 1  # not marked checked: asked again next run
                verdict, card, reason = "NO_VERDICT", "", ""
            else:
                judged.write(f"{fix['log_id']}\n")
                if result.is_valid:
                    continue
                disagreements += 1
                verdict, reason = result.verdict, result.reason or ""
                card = (f"{result.corrected_word or fix['word']} = {result.corrected_translation}"
                        if verdict == "FIX" else "")
            out.writerow([fix["log_id"], fix["fixed_at"], fix["new_meaning_id"], fix["active_words"],
                          fix["word"], fix["translation"], fix["fixed_from"], verdict, card, reason,
                          fix["context"]])

    print(f"{disagreements} of {len(rows)} fixes judged differently today, {no_verdict} without a verdict; "
          f"written to {args.out}, most active words first")


if __name__ == "__main__":
    main()

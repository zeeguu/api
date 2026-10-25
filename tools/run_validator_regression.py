#!/usr/bin/env python
"""
Score the translation validator against its regression set.

    python -m tools.run_validator_regression [--runs 3] [--only "vil sige"] [--save]

Reads zeeguu/core/llm_services/regression/translation_validator.yaml and asks
the validator about every case, `--runs` times each (it runs at temperature 0
but is not deterministic). A run passes when the verdict is one of `expect` and,
for a FIX, the corrected card is one of `card` (case-insensitive).

With --save, the report is also written to
zeeguu/core/llm_services/regression/results/translation_validator/<prompt version>--<date>.txt,
so every prompt version keeps the run it was judged by.

No database: the validator only needs ANTHROPIC_API_KEY.
"""
import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.core.llm_services.prompts.translation_validator import PROMPT_VERSION
from zeeguu.core.llm_services.translation_validator import TranslationValidator

REGRESSION = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "zeeguu/core/llm_services/regression"
)
SET = os.path.join(REGRESSION, "translation_validator.yaml")
RESULTS = os.path.join(REGRESSION, "results", "translation_validator")


def as_list(value):
    return value if isinstance(value, list) else [value]


def normalized(card):
    word, translation = (part.strip().lower() for part in card.split("=", 1))
    return word, translation


def verdict_of(result):
    if result is None:
        return "NO_VERDICT", None
    if result.verdict != "FIX":
        return result.verdict, None
    return "FIX", (result.corrected_word, result.corrected_translation)


def passes(case, verdict, fix):
    if verdict not in as_list(case["expect"]):
        return False
    if verdict != "FIX":
        return True
    word = (fix[0] or case["word"]).strip().lower()
    translation = (fix[1] or case["translation"]).strip().lower()
    return (word, translation) in [normalized(card) for card in as_list(case["card"])]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--only", help="only cases for this word")
    parser.add_argument("--save", action="store_true", help="also write the report to the results folder")
    args = parser.parse_args()

    with open(SET) as f:
        cases = yaml.safe_load(f)["cases"]
    if args.only:
        cases = [c for c in cases if c["word"] == args.only]

    validator = TranslationValidator()

    def ask(case):
        return validator.validate_and_classify(
            case["word"],
            case["translation"],
            case["context"],
            case.get("source", "da"),
            case.get("target", "en"),
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(ask, [case for case in cases for _ in range(args.runs)]))

    report = [f"{PROMPT_VERSION}, {TranslationValidator.MODEL_NAME}, {date.today()}, {args.runs} run(s) per case"]
    passed = total = 0
    for i, case in enumerate(cases):
        outcomes = []
        for result in replies[i * args.runs : (i + 1) * args.runs]:
            verdict, fix = verdict_of(result)
            ok = passes(case, verdict, fix)
            passed += ok
            total += 1
            shown = f"{fix[0] or case['word']} = {fix[1] or case['translation']}" if fix else verdict
            outcomes.append(("ok " if ok else "BAD") + " " + shown)
        wanted = case["expect"] if case["expect"] != "FIX" else case["card"]
        report.append(f"{case['word']} = {case['translation']!r} -> want {wanted}")
        report.extend(f"    {outcome}" for outcome in outcomes)

    report.append(f"\n{passed}/{total} runs pass")
    print("\n".join(report))
    if args.save and not args.only:
        os.makedirs(RESULTS, exist_ok=True)
        path = os.path.join(RESULTS, f"{PROMPT_VERSION}--{date.today()}.txt")
        with open(path, "w") as f:
            f.write("\n".join(report) + "\n")
        print(f"Saved to {path}")


if __name__ == "__main__":
    main()

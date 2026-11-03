#!/usr/bin/env python
"""
Score the disagreement resolver against its regression set.

    python -m tools.run_disagreement_regression [--runs 3] [--only "en bonde"] [--save]

Reads zeeguu/core/llm_services/regression/translation_disagreement.yaml and
asks the resolver about every case, `--runs` times each. A run passes when
the translation is one of `expect` (case-insensitive).

With --save, the report is also written to
zeeguu/core/llm_services/regression/results/translation_disagreement/<prompt version>--<date>.txt,
so every prompt version keeps the run it was judged by.

No database: the resolver only needs ANTHROPIC_API_KEY.
"""
import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.core.llm_services import models
from zeeguu.core.llm_services.prompts.translation_disagreement import PROMPT_VERSION
from zeeguu.core.llm_services.translation_disagreement_resolver import resolve_translation_disagreement

REGRESSION = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "zeeguu/core/llm_services/regression"
)
SET = os.path.join(REGRESSION, "translation_disagreement.yaml")
RESULTS = os.path.join(REGRESSION, "results", "translation_disagreement")


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

    def ask(case):
        return resolve_translation_disagreement(
            case["word"],
            case["context"],
            case["candidates"],
            case.get("source", "da"),
            case.get("target", "en"),
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(ask, [case for case in cases for _ in range(args.runs)]))

    report = [f"{PROMPT_VERSION}, {models.TRANSLATION_DISAGREEMENT}, {date.today()}, {args.runs} run(s) per case"]
    passed = total = 0
    for i, case in enumerate(cases):
        wanted = [e.lower() for e in case["expect"]]
        report.append(f"{case['word']} {case['candidates']} -> want {case['expect']}")
        for result in replies[i * args.runs : (i + 1) * args.runs]:
            ok = bool(result) and result.translation.lower() in wanted
            passed += ok
            total += 1
            shown = f"{result.translation!r}  ({result.reason})" if result else "NO_ANSWER"
            report.append(f"    {'ok ' if ok else 'BAD'} {shown}")

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

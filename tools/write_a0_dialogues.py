#!/usr/bin/env python
"""
Write A0 dialogues for the newest Evergreen articles of a language, by hand:
for articles older than the crawl-time ones (zeeguu.core.content_retriever.a0_dialogues),
or to try a batch.

Each dialogue is written from the article's summary, checked by a second model,
rewritten from the checker's notes at most twice, and kept only if it passes
(zeeguu.core.llm_services.a0_article_dialogue). Kept dialogues are saved as
their own articles, read in the reader "inspired by" the article
(zeeguu.core.model.article_dialogue).

Usage:
  python -m tools.write_a0_dialogues da                  # dry run: write and print, save nothing
  python -m tools.write_a0_dialogues da --count 30 --apply
  python -m tools.write_a0_dialogues da --keyword ulv --apply

A dry run still pays for the LLM calls (2 to 6 DeepSeek calls per article). Articles that
already inspired a dialogue are skipped, so a run can be repeated.
"""

import argparse

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.content_retriever.a0_dialogues import candidates
from zeeguu.core.llm_services.a0_article_dialogue import CHECKER, WRITER, write_a0_dialogue
from zeeguu.core.model import Language
from zeeguu.core.model.article_dialogue import ArticleDialogue


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("language", help="language code, e.g. da")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--keyword", help="only articles whose title or summary mention this")
    parser.add_argument("--apply", action="store_true", help="save the dialogues that pass")
    args = parser.parse_args()

    language = Language.find(args.language)
    articles = candidates(language, args.count, args.keyword)
    print(f"{len(articles)} {language.name} Evergreen articles; {'saving' if args.apply else 'dry run'}\n")

    kept = 0
    for article in articles:
        result = write_a0_dialogue(language.name, article.title, article.summary)
        checks = ", ".join(a.check["verdict"] if a.check else "malformed" for a in result.attempts)
        print(f"### {article.id} {article.title}")
        print(f"    checks: {checks or '-'}")
        if not result.accepted:
            print(f"    dropped: {result.skip_reason}\n")
            continue
        kept += 1
        print(f"    title: {result.title}")
        for speaker, text in result.lines:
            print(f"    {speaker}: {text}")
        if args.apply:
            dialogue = ArticleDialogue.create(db.session, article, result.title, result.lines, WRITER, CHECKER)
            db.session.commit()
            print(f"    saved as article {dialogue.article_id}")
        print()

    print(f"{kept} of {len(articles)} passed{' and were saved' if args.apply else ''}.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""
Backfill: strip scraped "published on <date>" fragments from article.authors.

Historically the crawler stored bylines like "Publiceret D., Søren Rosenberg
Pedersen" or "Publié Le Mai À", where the leading part is a publish-date line
the scraper mistook for an author. New articles are cleaned at ingestion (see
zeeguu.core.util.authors.clean_authors, called from Article.__init__); this
one-off repairs the ~30k rows already in the database.

Dry-run by default — prints what WOULD change. Pass --commit to write.

Usage:
    python -m tools.clean_junk_authors            # dry run, show samples
    python -m tools.clean_junk_authors --limit 50 # dry run, only first 50
    python -m tools.clean_junk_authors --commit    # apply the changes
"""
import sys

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.model.article import Article
from zeeguu.core.util.authors import clean_authors

# Broad pre-filter so we don't scan every article; clean_authors() makes the
# precise per-row decision, and we only UPDATE rows that actually change.
_CANDIDATE_REGEX = (
    "Publiceret|Publicerad|Publisert|Publié|Publie|Published|"
    "Veröffentlicht|Pubblicato|Publicado|Gepubliceerd|Julkaistu|"
    "Opdateret|Uppdaterad|Oppdatert|Updated|Aktualisiert"
)

COMMIT_BATCH = 500


def main():
    commit = "--commit" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    query = Article.query.filter(Article.authors.op("REGEXP")(_CANDIDATE_REGEX))
    if limit:
        query = query.limit(limit)

    candidates = query.all()
    print(f"Scanning {len(candidates)} candidate articles "
          f"({'COMMIT' if commit else 'DRY RUN'})...\n")

    changed = 0
    emptied = 0
    samples_shown = 0
    for article in candidates:
        old = article.authors
        new = clean_authors(old)
        if new == old:
            continue
        changed += 1
        if new == "":
            emptied += 1
        if samples_shown < 25:
            print(f"  #{article.id}: {old!r}")
            print(f"        -> {new!r}\n")
            samples_shown += 1
        if commit:
            article.authors = new
            if changed % COMMIT_BATCH == 0:
                db.session.commit()
                print(f"  ... committed {changed} so far")

    if commit:
        db.session.commit()

    print(
        f"\nDone. {changed} articles would change"
        f" ({emptied} emptied to no author)."
        + ("" if commit else "  Re-run with --commit to apply.")
    )


if __name__ == "__main__":
    main()

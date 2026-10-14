#!/usr/bin/env python
"""
One-off: send validated meanings whose translation lists options back to the
validator.

"som skal = which must/which should" and "ved at = by (doing something)"
were marked validated before the validator learned to insist on one
translation, and validated meanings are never checked again. Resetting them
to NOT_VALIDATED makes ValidationService re-check each before its next
exercise; the validator now reduces such translations to one option.

Dates, slashes the source word has too (roll-on/roll-off) and glosses that
are in the source word ("... (ICE)") are left alone; see single_translation.

Usage:
    python -m tools.revalidate_translations_with_options          # dry run: list them
    python -m tools.revalidate_translations_with_options --apply
"""

import argparse

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from sqlalchemy import or_
from sqlalchemy.orm import aliased

from zeeguu.core.llm_services.single_translation import lists_options, pick_one
from zeeguu.core.model import Meaning, Phrase


def meanings_listing_options():
    Translation = aliased(Phrase)
    candidates = (
        Meaning.query.join(Translation, Translation.id == Meaning.translation_id)
        .filter(Meaning.validated == Meaning.VALID)
        .filter(or_(Translation.content.contains("/"), Translation.content.contains("(")))
        .order_by(Meaning.id)
        .all()
    )
    return [m for m in candidates if lists_options(m.translation.content, m.origin.content)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="reset them (default: dry run)")
    args = parser.parse_args()

    meanings = meanings_listing_options()
    for m in meanings:
        print(
            f"{m.id}\t{m.origin.content}\t{m.translation.content}"
            f"\t(fallback if the validator keeps listing: {pick_one(m.translation.content, m.origin.content)})"
        )
    print(f"{len(meanings)} validated meanings list options in their translation.")

    if not args.apply:
        print("Dry run. Pass --apply to send them back to the validator.")
        return

    for m in meanings:
        m.validated = Meaning.NOT_VALIDATED
    db.session.commit()
    print(f"Reset {len(meanings)} to NOT_VALIDATED.")


if __name__ == "__main__":
    main()

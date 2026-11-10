#!/usr/bin/env python
"""
Creates or updates a word list from a TSV file with a header row and the
columns `danish`/`phrase`, `english`/`translation`, `example`, `section`
(the first column name of each pair that is present is used).

Running it again with a corrected file updates the list in place. Without
--apply it only reports what would change.

    python -m tools.import_word_list --name PD3 --language da --translation-language en \\
        --description "..." --origin "..." path/to/list.tsv [--apply]
"""
import argparse
import csv
import os
import sys

from sqlalchemy.exc import NoResultFound

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.model.language import Language
from zeeguu.core.model.word_list import WordList

COLUMNS = {
    "phrase": ("phrase", "danish"),
    "translation": ("translation", "english"),
    "example": ("example",),
    "section": ("section",),
}

parser = argparse.ArgumentParser()
parser.add_argument("path")
parser.add_argument("--name", required=True)
parser.add_argument("--language", required=True, help="code of the entries' language")
parser.add_argument("--translation-language", help="code of the translations' language")
parser.add_argument("--description")
parser.add_argument("--origin", help="where the list came from")
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()


def column(header, field):
    for name in COLUMNS[field]:
        if name in header:
            return name
    return None


with open(args.path, newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")
    names = {field: column(reader.fieldnames, field) for field in COLUMNS}
    if not names["phrase"]:
        sys.exit(f"no phrase column in {reader.fieldnames}")
    rows = [{field: row[name] for field, name in names.items() if name} for row in reader]

def language_or_exit(code):
    try:
        return Language.find(code)
    except NoResultFound:
        sys.exit(f"unknown language code: {code}")


language = language_or_exit(args.language)
translation_language = language_or_exit(args.translation_language) if args.translation_language else None

word_list = WordList.find(args.name, language)
if word_list is None:
    word_list = WordList(name=args.name, language=language)
    db.session.add(word_list)
    print(f"new list {args.name} ({args.language})")
word_list.translation_language = translation_language
if args.description is not None:
    word_list.description = args.description
if args.origin is not None:
    word_list.origin = args.origin

added, updated, removed = word_list.import_entries(rows)
print(f"{len(rows)} rows: {added} added, {updated} updated, {removed} removed; "
      f"{len(word_list.entries)} entries")

if args.apply:
    db.session.commit()
    print(f"saved: word_list {word_list.id}")
else:
    db.session.rollback()
    print("dry run; --apply to save")

# This script fixes backwards all the Article contents in the DB
# by "flattening" composed unicode characters,
# like the two-character-å into a single-character-å
from sys import argv

from zeeguu.core.content_cleaning.unicode_normalization import flatten_composed_unicode_characters
from zeeguu.core.model import Article, Language
from zeeguu.core.model import db


def flatten_the_unicode_characters(language):
    all_danish_articles = Article.query.filter_by(language_id=language.id).all()

    print(f"Processing {len(all_danish_articles)} articles in: {language.name}\n...")

    counter = 0
    fixed = 0
    for each in all_danish_articles:
        flattened = flatten_composed_unicode_characters(each.content)
        if flattened != each.content:
            fixed += 1
            print(f"Fixing article with id: {each.id}")
            each.content = flattened
            db.session.add(each)

        counter += 1
        if counter % 10000 == 0:
            print(f"... {counter}")

    db.session.commit()
    db.session.close()

    print(f"Fixed a total of: {fixed} articles!")


if __name__ == '__main__':
    if len(argv) < 2:
        print("ERROR: Provide language code as argument")
        exit(-1)

    language = Language.find_or_create(argv[1])
    print(f"Looking up articles in: {language.name}")

    flatten_the_unicode_characters(language)

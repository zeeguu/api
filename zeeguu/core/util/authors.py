import re

"""
    Sanitize the `authors` byline that scrapers extract from articles.

    Newspaper/readability parsing frequently mistakes a publisher's
    "published on <date>" line for an author, so the byline ends up like

        "Publiceret D., Søren Rosenberg Pedersen"   (da)
        "Publié Le Mai À"                           (fr)
        "Pubblicato il 18/07/2022 ... By ..."       (it)

    These date fragments then render as the article's author. We drop any
    comma-separated part that begins with a known "published"/"updated" verb
    and keep the genuine names. If nothing genuine remains, the result is an
    empty string (the caller then falls back to the uploader or shows none).

    This is intentionally conservative: it only removes parts that *start*
    with a publish/update verb, so real names are never discarded.
"""

# Publish/update verbs across the languages Zeeguu crawls (da, fr, sv, no, en,
# de, it, es/pt, nl, fi). Matched case-insensitively, anchored at the start of a
# byline part, on a word boundary — so "Published"/"Publié"/"Publiceret" are
# junk, but a real name like "Publio" or "Publius" is not.
_JUNK_AUTHOR_PREFIX = re.compile(
    r"^(?:"
    r"publiceret|publicerad|publisert|publié|publie|published|"
    r"veröffentlicht|veroffentlicht|pubblicato|publicado|"
    r"gepubliceerd|julkaistu|"
    r"opdateret|uppdaterad|oppdatert|updated|aktualisiert|"
    r"mis à jour|actualizado|aggiornato"
    r")\b",
    re.IGNORECASE | re.UNICODE,
)


def clean_authors(authors):
    """Strip scraped "published on <date>" fragments from a byline string.

    :param authors: raw comma-separated author string (or falsy)
    :return: cleaned comma-separated string; "" if only junk remained
    """
    if not authors:
        return authors

    kept = []
    for part in authors.split(","):
        # Collapse the newline/tab runs scrapers leave behind so the prefix
        # check sees the real leading token (e.g. "Publiceret d. 14.05.22\n Af").
        part = re.sub(r"\s+", " ", part).strip()
        if not part:
            continue
        if _JUNK_AUTHOR_PREFIX.match(part):
            continue
        kept.append(part)

    return ", ".join(kept)

"""
Regional varieties of the languages Zeeguu teaches.

A variety is NOT a language. Flemish is Dutch; Brazilian Portuguese is
Portuguese. A learner of either keeps one vocabulary, one tokenizer, one set of
frequency lists and one Elasticsearch language. What a variety decides is
everything *above* that line: which sources the feed prefers, which voice reads
the audio lesson, which target the translator is asked for, and what the LLM is
told the text should be written in.

Keeping it out of the `language` table is the whole point. A separate row would
fork `phrase.language_id`, and with it the user's word history, the shared
meanings, and every cached translation and example sentence -- for two
vocabularies that overlap almost entirely.

A variety is identified by the country it belongs to, so a learner's preference
and a feed's `country` compare directly. That also keeps the catalogue honest:
only languages that genuinely divide along national lines belong here. Spanish
does not -- its split is Spain against a macro-region (es-419), which no country
code can express -- so it stays out until somebody asks for it and answers that
question.

Belgium appears twice, under Dutch and under French, which is the country being
bilingual rather than a mistake: a learner of either can want to read the half of
Belgium that speaks theirs.

What is listed here is what CAN be offered. What IS offered is narrower: see
catalogue(), which asks the feeds. A variety nobody publishes from is a trap, and
one that appears the day a feed is added needs nobody to remember it.
"""

# language code -> the countries whose variety a learner can ask for.
# The first entry is the one Zeeguu has historically served by default (see the
# hardcoded pt-PT in the DeepL target and in the audio-lesson voice config); it
# is NOT applied automatically, because no preference has to keep meaning
# "whatever the feed offers".
VARIETIES = {
    "nl": ("NL", "BE"),
    "fr": ("FR", "BE"),
    "pt": ("PT", "BR"),
}

# What to call a variety when a person -- or an LLM prompt -- has to read it.
# Where a variety has its own adjective in English, that is what it is called.
# Where it does not -- there is no adjective for "the French of France" that is
# not just "French" -- say it the long way rather than invent one: these names go
# into LLM prompts, where "Netherlands Dutch" is a phrase to puzzle over and
# "Dutch from the Netherlands" is an instruction.
VARIETY_NAMES = {
    ("nl", "NL"): "Dutch from the Netherlands",
    ("nl", "BE"): "Belgian Dutch",
    ("fr", "FR"): "French from France",
    ("fr", "BE"): "Belgian French",
    ("pt", "PT"): "European Portuguese",
    ("pt", "BR"): "Brazilian Portuguese",
}


def varieties_for(language_code: str):
    """The countries offering a variety of this language; empty when it has none."""
    return VARIETIES.get(language_code, ())


def has_varieties(language_code: str) -> bool:
    return bool(varieties_for(language_code))


def is_supported(language_code: str, country: str) -> bool:
    return country in varieties_for(language_code)


def variety_name(language_code: str, country: str) -> str:
    """'Belgian Dutch'. Falls back to the language's own name for anything unknown."""
    from zeeguu.core.language.language_codes import language_name

    return VARIETY_NAMES.get((language_code, country)) or language_name(language_code)


def countries_with_feeds():
    """
    {"nl": {"NL", "BE"}, ...} -- the countries some live feed actually publishes
    from, per language. Deactivated feeds do not count: they keep no content
    coming, so a variety resting on one is a variety with nothing behind it.
    """
    from zeeguu.core.model.db import db
    from zeeguu.core.model.feed import Feed
    from zeeguu.core.model.language import Language

    rows = (
        db.session.query(Language.code, Feed.country)
        .join(Feed, Feed.language_id == Language.id)
        .filter(Feed.country.isnot(None))
        .filter(Feed.deactivated == 0)
        .distinct()
        .all()
    )

    supplied = {}
    for language_code, country in rows:
        supplied.setdefault(language_code, set()).add(country)
    return supplied


def catalogue():
    """
    The varieties worth offering, shaped for the client that renders the control:
    {"nl": [{"country": "NL", "name": "Belgian Dutch"}, ...], ...}

    A language appears here once feeds publish from at least TWO of its
    countries, and stops appearing when they do not. One is not enough: with
    every Portuguese feed tagged PT, "Any" and "Portugal" would select the same
    articles. Offering one with nothing behind it is a trap
    -- a learner picks it, gets an empty feed, and concludes the app is broken --
    and the alternative, remembering to switch it on the day a feed is added, is
    a step nobody will remember. Brazilian Portuguese is the live example: named
    here, unofferable until somebody adds a Brazilian feed, offered the moment
    they do, without a deploy.

    Availability comes from the feeds; the NAMES stay in VARIETY_NAMES, because
    "Brazilian Portuguese" is knowledge the database does not have.

    This is deliberately NOT what validates a saved preference. is_supported()
    still answers from VARIETIES, so a learner whose country loses its last feed
    keeps the setting they chose rather than having a save rejected; their feed
    goes empty, and the client explains that and offers the way back.
    """
    supplied = countries_with_feeds()

    offered = {}
    for language_code, countries in VARIETIES.items():
        available = [c for c in countries if c in supplied.get(language_code, set())]
        # Two, not one. With every Portuguese feed tagged PT, a control offering
        # "Any" and "Portugal" is two labels for the same set of articles -- a
        # choice that cannot change anything, which is worse than no choice.
        if len(available) > 1:
            offered[language_code] = [
                dict(country=country, name=variety_name(language_code, country))
                for country in available
            ]
    return offered

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
"""

# language code -> the countries whose variety a learner can ask for.
# The first entry is the one Zeeguu has historically served by default (see the
# hardcoded pt-PT in the DeepL target and in the audio-lesson voice config); it
# is NOT applied automatically, because no preference has to keep meaning
# "whatever the feed offers".
VARIETIES = {
    "nl": ("NL", "BE"),
    "pt": ("PT", "BR"),
}

# What to call a variety when a person -- or an LLM prompt -- has to read it.
VARIETY_NAMES = {
    ("nl", "NL"): "Netherlands Dutch",
    ("nl", "BE"): "Belgian Dutch",
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


def catalogue():
    """
    The whole table, shaped for the client that renders the variety control:
    {"nl": [{"country": "NL", "name": "Netherlands Dutch"}, ...], ...}

    Served from here so the web app does not keep a second copy of a list that
    has to agree with what the feeds are tagged with.
    """
    return {
        language_code: [
            dict(country=country, name=variety_name(language_code, country))
            for country in countries
        ]
        for language_code, countries in VARIETIES.items()
    }

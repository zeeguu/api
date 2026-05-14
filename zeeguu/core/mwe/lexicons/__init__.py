"""
Per-language hand-curated MWE lexicons.

These complement the dependency-parser-based detection in
`stanza_mwe_detector.py` by catching fixed/semi-fixed expressions
that Stanza's `compound:prt` / `aux` / `det` rules cannot see —
chiefly prepositional idioms ("på jagt efter", "im Hinblick auf",
"in spite of") and light-verb constructions.

A lexicon is a `frozenset[str]` of lowercased surface forms, one
phrase per entry, words separated by single spaces.

Future work: bulk-seed these from UD `fixed` relations + Wiktionary
"<lang> idioms" / "<lang> prepositional phrases" categories via
`tools/extract_mwes_from_ud.py`.
"""

from typing import FrozenSet

from .da import DANISH_MWES
from .de import GERMAN_MWES
from .en import ENGLISH_MWES
from .nl import DUTCH_MWES
from .no import NORWEGIAN_MWES
from .sv import SWEDISH_MWES


LEXICONS_BY_LANGUAGE: dict[str, FrozenSet[str]] = {
    "da": DANISH_MWES,
    "de": GERMAN_MWES,
    "en": ENGLISH_MWES,
    "nl": DUTCH_MWES,
    "no": NORWEGIAN_MWES,
    "sv": SWEDISH_MWES,
}


def get_lexicon(language_code: str) -> FrozenSet[str]:
    """Return the MWE lexicon for `language_code`, or empty frozenset."""
    return LEXICONS_BY_LANGUAGE.get(language_code, frozenset())

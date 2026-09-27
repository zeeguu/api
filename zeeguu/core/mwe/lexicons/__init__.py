"""
Per-language hand-curated MWE lexicons.

These complement the dependency-parser-based detection in
`stanza_mwe_detector.py` by catching fixed/semi-fixed expressions
that Stanza's `compound:prt` / `aux` / `det` rules cannot see —
chiefly prepositional idioms ("på jagt efter", "im Hinblick auf",
"in spite of") and light-verb constructions.

A lexicon is a `frozenset[str]` of lowercased forms, one phrase per
entry, words separated by single spaces.

Each language has up to two: a surface-matched set, and an optional
verb-initial set matched with the first token lemmatised (only the
leading verb inflects). Danish has the verb set; the others are
surface-only for now, for two different reasons:

  - da / no / sv / en put the verb first ("tage hensyn til", "take
    into account"), so lemmatising token 0 is enough. Their light-verb
    entries currently match only in the infinitive -- the same latent
    bug Danish had. Mechanical to fix, not yet verified per language.
  - de / nl put the verb last ("in Betracht ziehen", "rekening houden
    met") and V2 order moves it out of the span entirely ("Ich ziehe
    das in Betracht"). Lemmatising a fixed position cannot help; these
    need the parser, not the lexicon.

Future work: bulk-seed these from UD `fixed` relations + Wiktionary
"<lang> idioms" / "<lang> prepositional phrases" categories via
`tools/extract_mwes_from_ud.py`.
"""

from typing import FrozenSet

from .da import DANISH_MWES, DANISH_VERB_MWES
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


# Verb-initial entries, matched with the first token lemmatised.
VERB_LEXICONS_BY_LANGUAGE: dict[str, FrozenSet[str]] = {
    "da": DANISH_VERB_MWES,
}


def get_lexicon(language_code: str) -> FrozenSet[str]:
    """Return the surface-matched MWE lexicon for `language_code`."""
    return LEXICONS_BY_LANGUAGE.get(language_code, frozenset())


def get_verb_lexicon(language_code: str) -> FrozenSet[str]:
    """Return the lemma-headed MWE lexicon for `language_code`."""
    return VERB_LEXICONS_BY_LANGUAGE.get(language_code, frozenset())

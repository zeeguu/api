"""
Danish multi-word expressions.

Hand-curated seed of fixed prepositional idioms and light-verb
constructions where Stanza's parser does not produce a usable
MWE grouping. Lowercased throughout; see the two sets below for
which of them is matched on surface form and which on the lemma.

Curation sources:
- Original seed: hand-picked from common Danish idioms
  (Den Danske Ordbog / Wiktionary "Danish prepositional phrases").
- 2026-05-14 expansion: candidate phrases mined from UD_Danish-DDT
  via the `fixed` dependency relation (tools/extract_mwes_from_ud.py).
  All additions are corpus-attested.

Two sets, because the two kinds of expression inflect differently:

DANISH_MWES is matched on surface form. These are frozen — "i dag"
means today and "i dagene" does not, so lemmatising them would group
the wrong span.

DANISH_VERB_MWES is matched with the first token lemmatised, because
these are verb-initial and only the verb inflects: "har brug for",
"havde brug for" and "have brug for" are the same expression. Without
this they only matched in the infinitive, which is the form a reader
almost never meets.
"""

DANISH_MWES = frozenset({
    # Prepositional idioms — "preposition + noun + preposition"
    # (non-verbal; see the package docstring on PARSEME labels)
    "på jagt efter",
    "på vej til",
    "på vej hjem",
    "på trods af",
    "på grund af",
    "på baggrund af",
    "på vegne af",
    "i stand til",
    "i forhold til",
    "i forbindelse med",
    "i henhold til",
    "i løbet af",
    "i stedet for",
    "i forvejen",
    "i gang",
    "i gang med",
    "i tvivl om",
    "til gengæld",
    "til trods for",
    "til fordel for",
    "til rådighed",
    "med hensyn til",
    "med henblik på",
    "ud over",
    "ud af",
    "for resten",
    "for det meste",
    "for så vidt",
    "af sted",
    "om bord",

    # ─── 2026-05-14: UD-DDT mined additions ────────────────────────────

    # Temporal "i + noun"
    "i dag",
    "den dag i dag",   # beats "i dag": "to this day", not "today"
    "i går",
    "i morgen",
    "i nat",
    "i aften",
    "i aftes",
    "i år",
    "i alt",
    "i øvrigt",
    "i hvert fald",
    "i det hele taget",
    "i går morges",
    "i går aftes",
    "i går eftermiddags",
    "i timevis",
    "i årevis",
    "i læssevis",

    # Weekday-past pattern "i [weekday]s" = last [weekday]
    "i mandags",
    "i tirsdags",
    "i onsdags",
    "i fredags",
    "i lørdags",

    # "til + noun" adverbials
    "til sidst",
    "til gode",
    "til stede",
    "til rette",
    "til tops",
    "til vejrs",
    "til lands",
    "til bords",
    "til fulde",
    "til døde",
    "til huse",

    # "for + noun"
    "for tiden",
    "for nylig",

    # "på + noun"
    "på tide",
    "på ny",

    # Conjunctions / connectors / discourse markers
    "selv om",
    "som om",
    "om end",
    "ikke desto mindre",
    "mere eller mindre",
    "alt imens",
    "bortset fra",
    "nu til dags",

    # "blandt + andet/andre"
    "blandt andet",
    "blandt andre",

    # Imperatives the lemmatiser gets wrong, kept here as plain surface forms.
    # "læg" lemmatises to "læge" (doctor), so "Læg mærke til" never reaches
    # the verb entry "lægge mærke til". The two sets compose: a lemmatiser
    # miss is patched with one literal string rather than by abandoning lemmas.
    "læg mærke til",

    # Other
    "ud af det blå",   # VID; beats "ud af": "out of the blue", not "out of"
    "stort set",
    "over bord",
    "simpelt hen",
    "en bloc",
    "a la carte",
})


# Verb-initial expressions, matched with the first token lemmatised (see the
# module docstring). Only the leading verb inflects; the tail is fixed, so
# "lagde mærke til" and "lægge mærke til" both reduce to one lookup.
DANISH_VERB_MWES = frozenset({
    # LVC — light-verb constructions
    "tage hensyn til",
    "tage stilling til",
    "give udtryk for",
    "have brug for",
    "have lyst til",
    "have ret til",
    "komme i tanke om",
    "lægge mærke til",
    "holde øje med",
    "sætte pris på",
    "stå over for",
    "være nødt til",
    "være glad for",
    "blive nødt til",

    # VPC — verb-particle constructions. The reason this set exists: "fandt ud af"
    # was being grouped as "ud af" ("out of") because that is a lexicon entry
    # and this one was not, so the reader was shown a confident translation of
    # a span that is not an expression.
    "finde ud af",
    "lade som om",     # beats "som om": "pretend", not "as if"

    # Learners fused these by hand repeatedly, which is the recall signal:
    # the detector never offered them. The parser reaches "slå op" only in
    # some frames -- "slog op med sin kæreste" yes, "slog op i ordbogen" no --
    # so the entry makes it consistent rather than adding something new.
    "finde sted",
    "slå op",
})

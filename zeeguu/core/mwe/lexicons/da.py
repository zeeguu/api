"""
Danish multi-word expressions.

Hand-curated seed of fixed prepositional idioms and light-verb
constructions where Stanza's parser does not produce a usable
MWE grouping. Lowercased surface forms.

Curation sources:
- Original seed: hand-picked from common Danish idioms
  (Den Danske Ordbog / Wiktionary "Danish prepositional phrases").
- 2026-05-14 expansion: candidate phrases mined from UD_Danish-DDT
  via the `fixed` dependency relation (tools/extract_mwes_from_ud.py).
  All additions are corpus-attested.
"""

DANISH_MWES = frozenset({
    # Prepositional idioms — "preposition + noun + preposition"
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

    # Light-verb constructions
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

    # ─── 2026-05-14: UD-DDT mined additions ────────────────────────────

    # Temporal "i + noun"
    "i dag",
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

    # Other
    "stort set",
    "over bord",
    "simpelt hen",
    "en bloc",
    "a la carte",
})

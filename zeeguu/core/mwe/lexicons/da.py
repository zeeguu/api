"""
Danish multi-word expressions.

Hand-curated seed of fixed prepositional idioms and light-verb
constructions where Stanza's parser does not produce a usable
MWE grouping. Lowercased surface forms.

Curation source: hand-picked from common Danish idioms (Den Danske
Ordbog / Wiktionary "Danish prepositional phrases"). Targeted at
forms a B1–C1 learner will hit weekly.
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
})

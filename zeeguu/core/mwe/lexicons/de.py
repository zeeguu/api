"""
German multi-word expressions.

Hand-curated seed of fixed prepositional idioms and light-verb
constructions. Lowercased surface forms.

Curation source: Wiktionary "German prepositional phrases" +
common Funktionsverbgefüge. Future work: bulk-seed from UD `fixed`.
"""

GERMAN_MWES = frozenset({
    # Prepositional idioms
    "im hinblick auf",
    "in bezug auf",
    "im laufe",
    "im laufe von",
    "im rahmen",
    "im rahmen von",
    "im gegensatz zu",
    "im vergleich zu",
    "im sinne von",
    "im zuge",
    "auf grund von",
    "aufgrund von",
    "im falle",
    "anstatt zu",
    "trotz allem",
    "vor allem",
    "von wegen",
    "nach wie vor",
    "in der lage",
    "in der regel",
    "in erster linie",
    "in der tat",
    "auf jeden fall",
    "auf keinen fall",
    "auf der suche nach",
    "auf der hut",
    "ab und zu",
    "hin und wieder",
    "nach und nach",
    "mit hilfe von",
    "an stelle von",

    # Light-verb constructions (Funktionsverbgefüge)
    "in betracht ziehen",
    "in frage stellen",
    "in kauf nehmen",
    "zur verfügung stellen",
    "zur verfügung stehen",
    "zur kenntnis nehmen",
    "zum ausdruck bringen",
    "zum einsatz kommen",
    "auf die nerven gehen",
    "rücksicht nehmen",
    "abschied nehmen",
})

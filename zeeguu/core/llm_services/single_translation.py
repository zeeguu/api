"""
A flashcard translation is one thing the learner can type: not "which
must/which should", not "by (doing something)".

The validator prompt asks for that, but the model doesn't always comply
(som skal = "which must/which should" got through on 22 Jan 2026, and
suo = "his/her" in July). These checks run on what it returns.

What stays: a "/" or "(...)" the source word has too ("roll-on/roll-off"),
a "/" between digits (dates like 09/10/2024), and a parenthetical whose
content is in the source word ("Immigration and Customs Enforcement (ICE)"
for "Einwanderungsbehörde ICE").
"""

import re

_PARENTHETICAL = re.compile(r"\s*\(([^()]*)\)")
_SLASH_BETWEEN_DIGITS = re.compile(r"(?<=\d)/(?=\d)")


def _parentheticals_to_drop(translation, word):
    if "(" in word:
        return []
    word_lower = word.lower()
    return [
        m for m in _PARENTHETICAL.finditer(translation)
        if m.group(1).strip().lower() not in word_lower
    ]


def _has_alternatives(translation, word):
    if "/" in word:
        return False
    return "/" in _SLASH_BETWEEN_DIGITS.sub("", translation)


def lists_options(translation, word):
    """True if the translation offers alternatives or a parenthetical gloss
    that the source word itself doesn't have."""
    if not translation:
        return False
    return _has_alternatives(translation, word) or bool(_parentheticals_to_drop(translation, word))


def pick_one(translation, word):
    """The translation reduced to one typeable option: the first "/"
    alternative, without glosses in parentheses. Returns it unchanged when
    there's nothing to drop, or when dropping would leave nothing."""
    result = translation
    for m in reversed(_parentheticals_to_drop(result, word)):
        result = result[: m.start()] + result[m.end():]
    if _has_alternatives(result, word):
        result = result.split("/")[0]
    result = " ".join(result.split())
    return result or translation

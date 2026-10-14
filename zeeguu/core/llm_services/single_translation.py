"""
A flashcard translation is one thing the learner can type: not "which
must/which should", not "by (doing something)".

The validator prompt asks for that, but the model doesn't always comply
(som skal = "which must/which should" got through on 22 Jan 2026, and
suo = "his/her" in July). These checks run on what it returns.

What stays, segment by segment (one exempt slash doesn't exempt the rest):
- a slash between digits: dates like 09/10/2024, "24/7";
- a slash inside a token the source word has too: "roll-on/roll-off",
  "Mannheim / Heidelberg" for "Mannheim/Heidelberg";
- the forms of one word: "твій/твоя/твоє/твої" for "your", "αυτοί/αυτές/αυτά"
  for "they". The source doesn't say which gender or number, and picking
  one would make the flashcard wrong for the others;
- a parenthetical whose words are all words of the source:
  "Immigration and Customs Enforcement (ICE)" for "Einwanderungsbehörde ICE";
- the translation of the source's own slashes and parentheticals, one for
  one and in order: "m / f" for "m/k", "ver (naar)" for "lointains (à)".
  Only the ones beyond what the source has are options.
"""

import os
import re

_PARENTHETICAL = re.compile(r"\s*\(([^()]*)\)")
_SPACED_SLASH = re.compile(r"\s*/\s*")
_TOKEN_EDGES = "\"'«»“”„.,;:!?()"


def _tokens(text):
    """Lower-cased words, with "a / b" written as "a/b"."""
    tokens = _SPACED_SLASH.sub("/", text.lower()).split()
    return {t.strip(_TOKEN_EDGES) for t in tokens} - {""}


def _parentheticals_to_drop(translation, word):
    word_tokens = _tokens(word)
    mirrored = len(_PARENTHETICAL.findall(word))  # the source's own, translated
    drop = []
    for m in _PARENTHETICAL.finditer(translation):
        gloss = _tokens(m.group(1))
        if gloss and gloss <= word_tokens:
            continue
        if gloss and mirrored:
            mirrored -= 1
            continue
        drop.append(m)
    return drop


def _alternative_slashes(translation, word):
    """(text, positions): the translation with "a / b" written as "a/b", and
    where in it the slashes are that separate alternatives."""
    text = _SPACED_SLASH.sub("/", translation)
    word_tokens = _tokens(word)
    positions = []
    matched = 0
    for token in re.finditer(r"\S+", text):
        if token.group().lower().strip(_TOKEN_EDGES) in word_tokens:
            matched += token.group().count("/")
            continue
        if _forms_of_one_word(token.group()):
            continue
        for slash in re.finditer("/", token.group()):
            i = token.start() + slash.start()
            if not _between_digits(text, i):
                positions.append(i)
    # The source's own slashes that weren't matched verbatim, translated.
    mirrored = len([i for i, c in enumerate(word) if c == "/" and not _between_digits(word, i)])
    return text, positions[max(mirrored - matched, 0):]


def _forms_of_one_word(token):
    """"твій/твоя/твоє/твої", "αυτοί/αυτές/αυτά", "nuevo/nueva": single words
    sharing a stem of at least two letters and half the shortest of them.
    "zo/dus" and "to/towards" are other words, not forms."""
    forms = [f.strip(_TOKEN_EDGES) for f in token.lower().split("/")]
    if len(forms) < 2 or not all(f.isalpha() for f in forms):
        return False
    stem = len(os.path.commonprefix(forms))
    shortest = min(len(f) for f in forms)
    return stem >= 2 and stem * 2 >= shortest and stem < shortest


def _between_digits(text, i):
    return 0 < i < len(text) - 1 and text[i - 1].isdigit() and text[i + 1].isdigit()


def lists_options(translation, word):
    """True if the translation offers alternatives or a parenthetical gloss
    that the source word itself doesn't have."""
    if not translation:
        return False
    return bool(_alternative_slashes(translation, word)[1]) or bool(
        _parentheticals_to_drop(translation, word)
    )


def pick_one(translation, word):
    """The translation reduced to one typeable option: up to the first
    alternative slash, without glosses in parentheses. Returns it unchanged
    when there's nothing to drop, or when dropping would leave nothing."""
    result = translation
    for m in reversed(_parentheticals_to_drop(result, word)):
        result = result[: m.start()] + result[m.end():]
    text, slashes = _alternative_slashes(result, word)
    if slashes:
        result = text[: slashes[0]]
    result = " ".join(result.split())
    return result or translation

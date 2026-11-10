"""
The CEFR levels: their order, and the one policy for a level between two.

Every comparison of levels goes through here. The database keeps its own
ENUMs (article.cefr_level, article_cefr_assessment.*), and the web its own
copy (src/utils/misc/cefrScale.js), which counts a split level the same way.

A split level ("B1/B2") is what ArticleCefrAssessment.update_effective_cefr_level
writes when the LLM and the ML assessment disagree by one step. It counts as
the HIGHER of the two everywhere: the question we ask of a level is nearly
always "is this too hard for the learner?", and too easy beats too hard.
"""

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")

# user_language.cefr_level stores an index into this; NULL means not set.
# A0 exists only for learners (and the audio lessons written for them):
# no text is assessed below A1.
STORED_LEVELS = ("A0",) + LEVELS


def is_level(value):
    """True for exactly one of A1..C2 (not a split level, not A0)."""
    return value in LEVELS


def parse(value):
    """Client input ("b1 ", "B1") as one of A1..C2, or None."""
    if not isinstance(value, str):
        return None
    value = value.strip().upper()
    return value if is_level(value) else None


def rank(level):
    """A1 -> 0 .. C2 -> 5; a split level ("B1/B2") ranks as its higher part;
    None for anything else (None, A0, garbage)."""
    if not level:
        return None
    ranks = [LEVELS.index(part) for part in level.split("/") if part in LEVELS]
    return max(ranks) if ranks else None


def single(level):
    """`level` as one of A1..C2: a split level counts as its higher part.
    None when there is no level in it."""
    r = rank(level)
    return None if r is None else LEVELS[r]


def up_to(level):
    """The levels at or below `level`, easiest first; [] when it is not a level."""
    r = rank(level)
    return [] if r is None else list(LEVELS[: r + 1])


def below(level):
    """The levels strictly below `level`, easiest first; [] when it is not a level."""
    r = rank(level)
    return [] if r is None else list(LEVELS[:r])


def is_above(level, other):
    """True when `level` is harder than `other`; False when either is not a level."""
    a, b = rank(level), rank(other)
    return a is not None and b is not None and a > b


def harder(level, other):
    """The harder of two levels. When one is missing, the other; when they
    cannot be compared, `level`."""
    if not level:
        return other
    if not other:
        return level
    a, b = rank(level), rank(other)
    if a is None or b is None:
        return level
    return other if b > a else level


def from_number(number):
    """The stored user_language.cefr_level (0..6) as A0..C2, or None."""
    if number is None or not 0 <= number < len(STORED_LEVELS):
        return None
    return STORED_LEVELS[number]


def to_number(level):
    """A0..C2 as the number user_language.cefr_level stores, or None."""
    return STORED_LEVELS.index(level) if level in STORED_LEVELS else None

"""
The CEFR levels: their order, and the one policy for a level between two.

Every comparison of levels goes through here. The database keeps its own
ENUMs (article.cefr_level, article_cefr_assessment.*), and the web its own
twin (src/utils/misc/cefr.js), which follows the same rules: keep the
two in step.

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
    if not isinstance(level, str):
        return None
    ranks = [LEVELS.index(part) for part in level.split("/") if part in LEVELS]
    return max(ranks) if ranks else None


def single(level):
    """`level` as one of A1..C2: a split level counts as its higher part.
    None when there is no level in it."""
    r = rank(level)
    return None if r is None else LEVELS[r]


def readable(level):
    """The level of the texts a learner at `level` reads, as one of A1..C2:
    A0 reads A1 (no text is written below A1), a split level its higher
    part. None when there is no level in it."""
    return "A1" if level == "A0" else single(level)


def combine(level, other):
    """One level out of two assessments of the same text (LLM and ML): the
    level when they agree, a split level ("B1/B2") when they are one step
    apart, the higher when further apart. When only one is a level, that
    one; when neither is, None."""
    a, b = rank(level), rank(other)
    if a is None or b is None:
        return single(level) or single(other)
    low, high = sorted((a, b))
    if high - low == 1:
        return f"{LEVELS[low]}/{LEVELS[high]}"
    return LEVELS[high]


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


def from_number(number):
    """The stored user_language.cefr_level (0..6) as A0..C2, or None."""
    if number is None or not 0 <= number < len(STORED_LEVELS):
        return None
    return STORED_LEVELS[number]


def to_number(level):
    """A0..C2 as the number user_language.cefr_level stores, or None."""
    return STORED_LEVELS.index(level) if level in STORED_LEVELS else None

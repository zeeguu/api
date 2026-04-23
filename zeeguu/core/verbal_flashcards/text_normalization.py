import re
import unicodedata


SANITIZED_SPOKEN_TEXT_PATTERN = re.compile(r"[^\w\sæøåÆØÅ']")
MULTISPACE_PATTERN = re.compile(r"\s+")
CANONICAL_DANISH_VARIANTS = (
    ("aa", "å"),
    ("ae", "æ"),
    ("oe", "ø"),
)
ASR_TOLERANT_DANISH_VARIANTS = (
    ("æ", "e"),
    ("ø", "o"),
    ("å", "a"),
)


def canonical_danish_form(word):
    """
    Normalize a word into a canonical written Danish form.

    This keeps Danish letters intact and only collapses common alternate
    spellings into their standard written forms.
    """
    if not word:
        return ""

    word = unicodedata.normalize("NFC", str(word).casefold())

    for pattern, replacement in CANONICAL_DANISH_VARIANTS:
        word = word.replace(pattern, replacement)

    return word


def asr_tolerant_danish_form(word):
    """
    Fold a word into a more ASR-tolerant comparison form.

    This starts from the canonical written form, then applies permissive
    simplifications that help match common ASR spellings to the expected word.
    """
    word = canonical_danish_form(word)

    if word.startswith("hv"):
        word = "v" + word[2:]

    if word.endswith("d"):
        word = word[:-1]
    if word.endswith("g"):
        word = word[:-1]

    for pattern, replacement in ASR_TOLERANT_DANISH_VARIANTS:
        word = word.replace(pattern, replacement)

    return word


def sanitize_spoken_text(text):
    """Keep Danish characters while normalizing whitespace and punctuation."""
    text = text.lower().strip() if text else ""
    text = SANITIZED_SPOKEN_TEXT_PATTERN.sub(" ", text)
    return MULTISPACE_PATTERN.sub(" ", text).strip()

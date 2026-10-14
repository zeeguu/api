from zeeguu.core.llm_services.translation_validator import TranslationValidator


def parse(text):
    # _parse_response uses no instance state; skip __init__ (needs an API key)
    return TranslationValidator._parse_response(object.__new__(TranslationValidator), text)


def test_bare_valid_line():
    r = parse("VALID|common|A1|single_word||")
    assert r.is_valid and r.frequency == "common" and r.phrase_type == "single_word"


def test_fix_after_reasoning_text():
    # Sonnet 5.5 with thinking off often explains before the verdict
    r = parse(
        '"Cumuler" means to accumulate. The Dutch "totaal" is a noun.\n\n'
        "FIX|cumule|cumuleert|common|B2|single_word|'totaal' is a noun||"
    )
    assert not r.is_valid
    assert (r.corrected_word, r.corrected_translation) == ("cumule", "cumuleert")


def test_valid_after_reasoning_is_classified():
    r = parse("Here 'hund' is plainly 'dog'.\nVALID|unique|A1|single_word||")
    assert r.is_valid and r.frequency == "unique"


def test_markdown_wrapped_verdict():
    r = parse("Reasoning.\n`FIX|pour cent|procent|common|A2|collocation|fragment||`")
    assert not r.is_valid and r.corrected_word == "pour cent"


def test_last_verdict_line_wins():
    r = parse(
        "Format is VALID|frequency|cefr|phrase_type|explanation|literal_meaning\n"
        "FIX|noget af|one of|common|B1|collocation|context-only gloss||something of"
    )
    assert not r.is_valid and r.corrected_word == "noget af"


def test_no_verdict_line_is_unclassified():
    r = parse("Cumuler means to accumulate, to total up, or to combine. In this")
    assert r.is_valid and r.frequency is None

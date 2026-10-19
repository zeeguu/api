from zeeguu.core.llm_services.prompts import CURRENT_PROMPT_VERSION, format_prompt, without_blanks


def test_examples_with_a_blank_or_underscores_are_dropped():
    examples = [
        {"sentence": "_____ est ton adresse e-mail ?"},
        {"sentence": "Vi har et godt Bolig_forhold_ her."},
        {"sentence": "Quelle est ton adresse e-mail ?"},
    ]
    assert without_blanks(examples) == [{"sentence": "Quelle est ton adresse e-mail ?"}]


def test_current_prompt_formats():
    prompt = format_prompt("selv", "even", "da", "en", "B1", CURRENT_PROMPT_VERSION)
    assert '"selv"' in prompt["user"] and '"even"' in prompt["user"]

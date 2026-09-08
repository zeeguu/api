"""
The reply shapes that used to lose a finished translation.

Both fixtures below are real replies from the 8 Sep 2026 failure of
/translate_and_adapt_article (Romanian -> Danish, A1): each provider had done
the work correctly, and `json.loads` threw the result away — Anthropic with
"Extra data", DeepSeek with "Invalid control character" — leaving the reader
with a 500 after two and a half minutes of waiting.
"""

from unittest import TestCase

from zeeguu.core.llm_services.simplification_service import parse_llm_json


# DeepSeek wrote the markdown content with real line breaks rather than \n,
# which strict JSON rejects inside a string.
DEEPSEEK_REPLY = """{
  "title": "Dopamin er ikke fjenden",
  "content": "## Hovedemne
I 2026 kan næsten alt give os glæde med det samme.

Men hvad sker der med os?",
  "summary": "Vi får for meget glæde."
}"""

# The translate prompt asks for two steps, so Haiku emitted one JSON object per
# step — the source-language translation first, then the adapted version we
# actually want, with a fence and a step heading in between.
ANTHROPIC_TWO_STEP_REPLY = """{
  "title": "Nu dopamina este dusmanul",
  "content": "## Dopamina nu este dusmanul\\n\\nIn 2026 traim intr-o lume ...",
  "summary": "Rezumat in romana."
}
```
---
# STEP 2: A1 CEFR SIMPLIFICATION (DANISH ONLY)
```json
{
  "title": "Dopamin er ikke fjenden",
  "content": "## Dopamin er ikke fjenden\\n\\nI 2026 lever vi i en verden.",
  "summary": "Dopamin er ikke fjenden."
}"""


class ParseLLMJsonTest(TestCase):
    def test_literal_newlines_inside_a_string_value(self):
        result = parse_llm_json(DEEPSEEK_REPLY)
        self.assertEqual("Dopamin er ikke fjenden", result["title"])
        self.assertIn("Hovedemne", result["content"])

    def test_two_step_reply_yields_the_final_step(self):
        result = parse_llm_json(ANTHROPIC_TWO_STEP_REPLY)
        self.assertEqual("Dopamin er ikke fjenden", result["title"])
        self.assertIn("I 2026 lever vi", result["content"])

    def test_fenced_single_object(self):
        result = parse_llm_json('```json\n{"title": "T", "content": "C"}\n```')
        self.assertEqual("T", result["title"])

    def test_prose_around_the_object(self):
        result = parse_llm_json('Here you go:\n{"title": "T", "content": "C"}\nHope that helps!')
        self.assertEqual("T", result["title"])

    def test_no_object_at_all(self):
        self.assertIsNone(parse_llm_json("I'm sorry, I can't help with that."))

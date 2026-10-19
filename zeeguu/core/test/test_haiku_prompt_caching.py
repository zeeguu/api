import os
from unittest import TestCase

from zeeguu.core.llm_services.haiku_client import _content
from zeeguu.core.llm_services.prompts.article_simplification import (
    get_assessment_and_summary_prompt,
)


class AssessmentPromptCachingTest(TestCase):
    def _prefix_and_prompt(self, title, content):
        template = get_assessment_and_summary_prompt("de")
        prompt = template.format(title=title, content=content)
        return os.path.commonprefix([template, prompt]), prompt

    def test_the_cached_prefix_is_the_same_for_every_article(self):
        a, _ = self._prefix_and_prompt("Wetter", "Es regnet.")
        b, _ = self._prefix_and_prompt("Bahn", "Der Zug ist spät.")
        self.assertEqual(a, b)
        self.assertNotIn("Wetter", a)

    def test_the_two_blocks_rebuild_the_prompt_and_only_the_first_is_cached(self):
        prefix, prompt = self._prefix_and_prompt("Wetter", "Es regnet.")
        blocks = _content(prompt, prefix)
        self.assertEqual(blocks[0]["text"] + blocks[1]["text"], prompt)
        self.assertIn("cache_control", blocks[0])
        self.assertNotIn("cache_control", blocks[1])

    def test_a_prompt_without_the_prefix_is_sent_as_is(self):
        self.assertEqual(_content("hello", None), "hello")
        self.assertEqual(_content("hello", "other"), "hello")
        self.assertEqual(_content("hello", "hello"), "hello")

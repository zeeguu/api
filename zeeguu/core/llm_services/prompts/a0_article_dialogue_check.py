"""
Prompt for checking an A0 dialogue written from an article (see
a0_article_dialogue) before any learner sees it. A0 learners copy what they
read and cannot spot a mistake, so the check is strict. On 11 Danish articles
(18 Nov 2026) it caught real errors in 9 of the first drafts: wrong tenses,
hedges dropped, the wrong person or object.
"""

PROMPT_VERSION = "a0-article-dialogue-check-v2"

A0_ARTICLE_DIALOGUE_CHECK_PROMPT = """You are a careful {language} teacher checking a dialogue for absolute beginners before learners see it. Learners at this level cannot spot mistakes, so be strict.

Article summary (the only allowed source of facts):
{summary}

Dialogue:
{dialogue}

List, in English, every real {language} error (grammar, word choice, phrasing a native speaker would not use) and every claim in the dialogue that the summary does not support or gets wrong. Only real problems: leaving out a detail is fine, and something you checked and found correct is not a problem, so do not list it. One short sentence per problem, saying what to change. Empty lists when there is nothing to fix. verdict: ok (nothing to fix), minor (only small wording issues), bad (a factual error or a real {language} mistake).

Reply with only a JSON object of this shape:
{{"language_errors": ["..."], "unsupported_claims": ["..."], "verdict": "ok"}}"""

A0_ARTICLE_DIALOGUE_CHECK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["language_errors", "unsupported_claims", "verdict"],
    "properties": {
        "language_errors": {"type": "array", "items": {"type": "string"}},
        "unsupported_claims": {"type": "array", "items": {"type": "string"}},
        "verdict": {"type": "string", "enum": ["ok", "minor", "bad"]},
    },
}


def create_a0_article_dialogue_check_prompt(language, summary, dialogue):
    return A0_ARTICLE_DIALOGUE_CHECK_PROMPT.format(language=language, summary=summary, dialogue=dialogue)

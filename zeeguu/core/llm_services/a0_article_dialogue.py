"""
Writes a short dialogue for absolute beginners (A0) from an article's summary,
and keeps it only if a second call, checking it like a strict teacher, finds
its facts and its language right.

Write, check; while the check finds problems, rewrite from its notes and check
again, at most MAX_REWRITES times. A dialogue is kept when the check says "ok",
or "minor" with nothing unsupported by the summary: small wording notes are
allowed, a wrong fact never is. A0 learners copy what they read and cannot
tell a mistake, so a dialogue that does not pass is dropped, not shown.

Run ahead of time by tools/write_a0_dialogues.py; nobody waits for it.
"""

import json
from dataclasses import dataclass, field

from zeeguu.core.llm_services import models
from zeeguu.core.llm_services.deepseek_service import DeepSeekService
from zeeguu.core.llm_services.prompts import a0_article_dialogue as writing
from zeeguu.core.llm_services.prompts import a0_article_dialogue_check as checking

MAX_REWRITES = 2
MIN_LINES, MAX_LINES = 4, 10
TIMEOUT_SECONDS = 180
REPLY_TOKENS = 2000


@dataclass
class Attempt:
    lines: list
    check: dict = None


@dataclass
class DialogueResult:
    """`lines` holds the accepted dialogue, or is None; `attempts` and
    `skip_reason` say why, for the tool's report."""

    title: str = ""
    lines: list = None  # [(speaker, text)] when accepted
    topic_words: list = field(default_factory=list)
    skip_reason: str = ""
    attempts: list = field(default_factory=list)

    @property
    def accepted(self):
        return bool(self.lines)


WRITER = (models.A0_DIALOGUE_WRITER, writing.PROMPT_VERSION)
CHECKER = (models.A0_DIALOGUE_CHECKER, checking.PROMPT_VERSION)


def _ask(model, prompt, schema):
    """One JSON reply. DeepSeek's JSON mode guarantees a JSON object, not the
    schema (which only documents the shape here): well_formed(), the defaults
    in write_a0_dialogue and _check cover a reply with missing parts."""
    reply = DeepSeekService(timeout=TIMEOUT_SECONDS)._make_deepseek_request(
        {"system": "You write and check short dialogues for language learners.", "user": prompt},
        max_tokens=REPLY_TOKENS,
        temperature=0.7,
        json_output=True,
    )
    return json.loads(reply)


def _check(language_name, summary, lines):
    check = _ask(
        models.A0_DIALOGUE_CHECKER,
        checking.create_a0_article_dialogue_check_prompt(language_name, summary, writing.as_text(lines)),
        checking.A0_ARTICLE_DIALOGUE_CHECK_SCHEMA,
    )
    return {
        "verdict": check.get("verdict") if check.get("verdict") in ("ok", "minor", "bad") else "bad",
        "language_errors": list(check.get("language_errors") or []),
        "unsupported_claims": list(check.get("unsupported_claims") or []),
    }


def passes(check):
    return check["verdict"] == "ok" or (check["verdict"] == "minor" and not check["unsupported_claims"])


def well_formed(lines):
    """Two speakers taking turns over a handful of one-line, non-empty lines."""
    return (
        MIN_LINES <= len(lines) <= MAX_LINES
        and all(isinstance(line, dict) and isinstance(line.get("speaker"), str) and isinstance(line.get("text"), str) for line in lines)
        and len({line["speaker"].strip() for line in lines}) == 2
        and all(line["speaker"].strip() and line["text"].strip() and "\n" not in line["text"] for line in lines)
    )


def write_a0_dialogue(language_name, title, summary):
    """A DialogueResult for the article with this title and summary."""
    result = DialogueResult()
    previous, notes = None, None
    for _ in range(1 + MAX_REWRITES):
        draft = _ask(
            models.A0_DIALOGUE_WRITER,
            writing.create_a0_article_dialogue_prompt(language_name, title, summary, previous, notes),
            writing.A0_ARTICLE_DIALOGUE_SCHEMA,
        )
        if draft.get("skip"):
            result.skip_reason = draft.get("skip_reason") or "skipped"
            return result
        draft.setdefault("title", "")
        draft.setdefault("topic_words", [])
        draft["lines"] = draft.get("lines") or []
        attempt = Attempt(draft["lines"])
        result.attempts.append(attempt)
        if not well_formed(draft["lines"]):
            notes = [f"Write {MIN_LINES} to {MAX_LINES} lines, each one line long, between exactly two speakers."]
            previous = draft["lines"]
            continue

        attempt.check = _check(language_name, summary, draft["lines"])
        if passes(attempt.check):
            result.title = draft["title"]
            result.topic_words = draft["topic_words"]
            result.lines = [(line["speaker"].strip(), line["text"].strip()) for line in draft["lines"]]
            return result
        previous = draft["lines"]
        notes = attempt.check["language_errors"] + attempt.check["unsupported_claims"]

    result.skip_reason = f"did not pass the check after {MAX_REWRITES} rewrites"
    return result

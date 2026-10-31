"""
Text simplification service using LLM providers (Anthropic and DeepSeek, each the other's fallback)
"""

import json
import os
import re
import requests
from typing import Dict, Optional
from zeeguu.logging import log
from zeeguu.core.language.generate_in_language import (
    LanguageMismatchError,
    generate_in_language,
)
from zeeguu.core.llm_services.haiku_client import HAIKU_MODEL, haiku_completion
from zeeguu.core.llm_services import models
from zeeguu.core.model.language import Language
from zeeguu.core.translation_services.deepl_translate import deepl_translate_article
from zeeguu.core.llm_services.prompts.level_simplification import (
    get_level_simplification_prompt,
    paragraphs,
)

# A whole article rewritten at one level, in one reply. A ~550-word article takes
# 8-13s with either provider; the learner waits, and a wrong-language reply is asked
# again before the next provider is tried, so the timeout bounds that wait 4 times over.
LEVEL_MAX_TOKENS = 8000

# A whole chapter translated in one reply runs at least as long as the input.
# Asked of both LLM translators; output_tokens caps it per model.
TRANSLATION_MAX_TOKENS = 16000
LEVEL_TIMEOUT = 60
TRANSLATION_TIMEOUT = 120


def _text_fields(result: Dict) -> list:
    """
    What must be in the requested language, for the output-language check.

    Title and summary are usually under the length threshold and come back as
    "can't judge"; the content is what actually decides.
    """
    return [
        ("title", result.get("title", "")),
        ("summary", result.get("summary", "")),
        ("content", result.get("content", "")),
    ]


def parse_llm_json(reply: str) -> Optional[Dict]:
    """
    Pull the result object out of an LLM reply, tolerating the two ways these
    replies routinely fail `json.loads` — both of which used to throw away a
    perfectly good translation and hand the reader a 500:

    1. Literal newlines inside string values. Models write markdown into
       `content` with real line breaks rather than `\n`; strict JSON rejects
       control characters in strings. `strict=False` accepts them.

    2. More than one JSON object in the reply. The translate prompts ask for a
       two-step job (translate, then adapt), and a model that takes the steps
       literally emits one object per step, sometimes with ``` fences and step
       headings between them. `json.loads` then fails with "Extra data". We
       decode every object and keep the last one that looks like a result —
       the final step's output, i.e. the adapted version we asked for.

    3. A backslash JSON does not know. The Markdown we send escapes a paragraph
       that opens with a speech dash as `\\-`, the prompt asks to keep it, and
       a model that copies it into a string value writes an invalid `\\-`
       escape. It is kept as the backslash it was meant to be.

    Returns None when nothing decodable is in there.
    """

    reply = re.sub(
        r"\\(.)",
        lambda m: m.group(0) if m.group(1) in '"\\/bfnrtu' else "\\\\" + m.group(1),
        reply,
        flags=re.S,
    )
    decoder = json.JSONDecoder(strict=False)
    objects = []
    index = 0
    while True:
        start = reply.find("{", index)
        if start == -1:
            break
        try:
            obj, end = decoder.raw_decode(reply, start)
        except ValueError:
            # Not the start of a complete object (a stray brace in prose, or a
            # truncated tail) — step past it and keep looking.
            index = start + 1
            continue
        if isinstance(obj, dict):
            objects.append(obj)
        index = end

    if not objects:
        return None
    with_content = [o for o in objects if o.get("content")]
    return (with_content or objects)[-1]


def _strip_markdown(text: str) -> str:
    """Remove markdown bold/italic formatting (summaries are plain text)."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)
    return text


def _clean(text: str) -> str:
    return text.strip().strip("[](){}\"'")


def _parse_fields(text: str, names: tuple, last: str) -> dict:
    """
    Parse 'NAME: value' sections (values may span lines). Once the `last` section
    starts, everything after it belongs to it.
    """
    fields, current = {}, None
    pattern = re.compile(rf"^\W*({'|'.join(names)})\W*:\s*(.*)$")
    for line in text.splitlines():
        if current == last:
            fields[current].append(line)
            continue
        match = pattern.match(line.strip())
        if match:
            current = match.group(1)
            fields[current] = [match.group(2)]
        elif re.match(r"^\s*\[\d+\]", line):
            # models sometimes skip the CONTENT: line and start with the numbered paragraphs
            current = last
            fields[current] = [line]
        elif current:
            fields[current].append(line)
    return {k: "\n".join(v).strip() for k, v in fields.items()}


def parse_level_reply(text: str, expected_paragraphs: int) -> Dict:
    """
    A reply to the level prompt (TITLE: / SUMMARY: / CONTENT: with [n]-numbered
    paragraphs) -> {title, content, summary}, content as plain paragraphs
    separated by blank lines. Raises if any of the three is missing.
    """
    fields = _parse_fields(text, ("TITLE", "SUMMARY", "CONTENT"), last="CONTENT")
    content = fields.get("CONTENT", "")
    # split on the [n] markers rather than on blank lines: models sometimes put the
    # numbered paragraphs on consecutive lines
    marker = re.compile(r"^\s*\[\d+\]\s*", re.MULTILINE)
    parts = marker.split(content) if marker.search(content) else paragraphs(content)
    paras = [p.strip() for p in parts if p.strip()]
    version = {
        "title": _clean(fields.get("TITLE", "")),
        "content": "\n\n".join(paras),
        "summary": _strip_markdown(_clean(fields.get("SUMMARY", ""))),
    }
    missing = [k for k, v in version.items() if not v]
    if missing:
        raise Exception(f"Unexpected response format, missing {missing}")
    if len(paras) != expected_paragraphs:
        log(f"  Warning: {len(paras)} paragraphs instead of {expected_paragraphs}")
    return version


def _title_rule(source_language: str, target_language: str) -> str:
    """
    A guard for the title, in the prompt of the LLM translators.

    Measured 2026-09-08 on ro->da: across every model and every prompt variant
    tried, the `summary` field carried the article's negation correctly and the
    `title` field did not -- same model, same JSON response. So this is not a
    comprehension failure and not the level constraints; the title alone
    anchors on the source's surface form. Romanian `Nu` (a negation) survived
    untranslated because it is also a Danish word meaning "now", which inverted
    the headline's claim and shipped to a reader.

    The guard therefore belongs on the title and not on the body's level rules.
    Those rules read as excessive, but they are load-bearing: softening them let
    B2 vocabulary into A1 output, pushed Sonnet past the max_tokens cap, and
    broke a title DeepSeek had previously got right.
    """
    return f"""TITLE - TRANSLATE IT, DO NOT ECHO IT:
The title is the likeliest place to make a meaning error, because it is short
and you are tempted to keep the original's shape. Do not.
- Read the original title, state its claim to yourself, then write that claim
  in {target_language} from scratch.
- NEVER keep a leading word from the {source_language} title because it is
  short or because that spelling also exists in {target_language}. It is a
  different word with a different meaning, and keeping it can reverse the
  title's claim.
- If the original title says something is NOT the case, your title must also
  say it is NOT the case, using a real {target_language} negation.
- Final check on the title alone: does it assert the SAME thing as the
  original, or the opposite? If the opposite, rewrite it."""


def _translation_prompt(title: str, content: str, source_language: str, target_language: str) -> str:
    """A full translation, its Markdown structure kept; the level comes after, from simplify_text."""
    return f"""Translate this {source_language} article into {target_language}, completely and faithfully: every sentence,
name, number and quote. Do not simplify, shorten or explain anything.

The article is in Markdown, one block per paragraph, blocks separated by blank lines. Return its blocks in the
same order, separated by blank lines. A block that starts with ## or ### is a heading: keep the marker. A block
that starts with - or 1. is a list item: keep the marker. A block that starts with > is a quote: keep the >. A
block that starts with \\- is a paragraph opening with a dash: keep the \\- exactly. Add no formatting.

{_title_rule(source_language, target_language)}

Respond in exactly this format, with no other text:
TITLE: <the title in {target_language}>
CONTENT:
<the article in {target_language}>

TITLE: {title}

{content}"""


def parse_translation_reply(reply: str) -> Dict:
    """
    The title and content of a reply to _translation_prompt: the TITLE: line,
    and everything after it. DeepSeek often leaves out the CONTENT: line, and a
    model may write a sentence before the TITLE: line.
    """
    match = re.search(r"^TITLE:(.*)$", reply, re.M)
    if not match:
        raise Exception("no TITLE: line in the translation")
    content = reply[match.end():].strip().removeprefix("CONTENT:").strip()
    if not content:
        raise Exception("no content in the translation")
    return {"title": match.group(1).strip(), "content": content}


class SimplificationService:
    """Service for text simplification. Each method says which provider goes first."""

    def __init__(self):
        self.anthropic_api_key = os.getenv("ANTHROPIC_TEXT_SIMPLIFICATION_KEY")
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_SIMPLIFICATIONS")

    def assess_cefr_level_deepseek_only(
        self, title: str, content: str, language_code: str = "ro"
    ) -> str:
        """
        Assess CEFR level using DeepSeek only (for consistency with batch crawling).
        Use this when creating clones/copies to ensure same model evaluates as during crawling.
        """
        if not self.deepseek_api_key:
            log("DEEPSEEK_API_SIMPLIFICATIONS not configured, falling back to LLM chain")
            cefr_level, topic, method = self.assess_cefr_and_topic_with_fallback(title, content, language_code)
            return cefr_level

        log(f"Using DeepSeek for CEFR assessment (consistency mode)")
        try:
            result = self._assess_cefr_deepseek(title, content, language_code)
            return result[0] if isinstance(result, tuple) else result
        except Exception as e:
            log(f"DeepSeek CEFR assessment failed: {e}")
            return None  # No assessment possible

    def assess_cefr_and_topic_with_fallback(
        self, title: str, content: str, language_code: str = "ro"
    ) -> tuple:
        """
        Assess CEFR level and topic using LLM fallback chain:
        - Try Anthropic first (fast, real-time)
        - Fall back to DeepSeek if Anthropic fails (slower, batch processing)

        Returns tuple: (cefr_level, topic, method)
        """
        # Try Anthropic first (faster for real-time use)
        if self.anthropic_api_key:
            log(f"Using Anthropic for real-time CEFR and topic assessment")
            try:
                result = self._assess_cefr_anthropic(title, content, language_code)
                if result:
                    # Add method info to result
                    cefr_level, topic = result
                    return (cefr_level, topic, "llm_assessed_anthropic")
            except Exception as e:
                log(f"Anthropic CEFR and topic assessment failed, falling back to DeepSeek: {e}")

        # Fallback to DeepSeek
        if self.deepseek_api_key:
            log(f"Using DeepSeek for batch CEFR and topic assessment")
            try:
                result = self._assess_cefr_deepseek(title, content, language_code)
                # Add method info to result
                cefr_level, topic = result
                return (cefr_level, topic, "llm_assessed_deepseek")
            except Exception as e:
                log(f"DeepSeek CEFR and topic assessment failed: {e}")

        log(
            "Neither ANTHROPIC_TEXT_SIMPLIFICATION_KEY nor DEEPSEEK_API_SIMPLIFICATIONS configured"
        )
        return (None, None, None)  # No assessment possible

    def simplify_text(
        self,
        title: str,
        content: str,
        target_level: str = "A2",
        language_code: str = "ro",
    ) -> Optional[Dict]:
        """
        Rewrite text at one CEFR level, paragraph by paragraph.

        DeepSeek goes first, with the strict prompt (hard per-level limits and a
        list of the original's words that are too rare for the level). Haiku is
        the fallback, with the plain prompt: strict hurt its faithfulness. See
        prompts/level_simplification.py for the evaluation behind this.

        Simplifying must not change the language. When the output comes back in
        another one it is re-requested once naming the mistake, and then given up
        on — the callers all treat None as "no simplified version".

        Returns: Dict with 'title', 'content' (HTML), 'summary' and 'model_name'
        (the model that wrote it), or None if failed
        """
        expected_paragraphs = len(paragraphs(content))
        providers = [
            ("DeepSeek", self.deepseek_api_key, models.DEEPSEEK_GENERAL, self._complete_deepseek),
            ("Anthropic", self.anthropic_api_key, HAIKU_MODEL, self._complete_haiku),
        ]
        for provider, api_key, model_name, complete in providers:
            if not api_key:
                continue
            log(f"Using {provider} for simplification to {target_level}")
            prompt = get_level_simplification_prompt(
                language_code, title, content, target_level, strict=provider == "DeepSeek"
            )

            def generate(correction):
                reply = complete(prompt + correction)
                if not reply:
                    raise Exception(f"{provider} returned no simplification")
                return parse_level_reply(reply, expected_paragraphs)

            try:
                version = generate_in_language(
                    generate,
                    language_code,
                    _text_fields,
                    f"{target_level} simplification of '{title[:50]}'",
                )
            except LanguageMismatchError as e:
                log(f"{provider} simplified into the wrong language: {e}")
                continue
            except Exception as e:
                log(f"{provider} simplification failed: {e}")
                continue

            import markdown2

            version["content"] = markdown2.markdown(
                version["content"],
                extras=["break-on-newline", "fenced-code-blocks", "tables"],
            )
            version["model_name"] = model_name
            return version

        log("No simplification provider succeeded (or none is configured)")
        return None

    def _complete_deepseek(
        self, prompt: str, max_tokens: int = LEVEL_MAX_TOKENS, timeout: int = LEVEL_TIMEOUT
    ) -> str:
        sent_max_tokens = models.output_tokens(models.DEEPSEEK_GENERAL, max_tokens)
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.deepseek_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": models.DEEPSEEK_GENERAL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": sent_max_tokens,
                "temperature": 0.1,
            },
            timeout=timeout,
        )
        if response.status_code != 200:
            raise Exception(f"DeepSeek API error: {response.status_code} - {response.text[:200]}")
        choice = response.json()["choices"][0]
        if choice.get("finish_reason") == "length":
            raise Exception(f"DeepSeek output truncated at max_tokens={sent_max_tokens}")
        return (choice["message"]["content"] or "").strip()

    def _complete_haiku(
        self, prompt: str, max_tokens: int = LEVEL_MAX_TOKENS, timeout: int = LEVEL_TIMEOUT
    ) -> Optional[str]:
        # None on API errors and on a reply cut off at max_tokens
        return haiku_completion(prompt, max_tokens=max_tokens, temperature=0.1, timeout=timeout)

    def translate_and_adapt(
        self,
        title: str,
        content: str,
        source_language: str,
        target_language: str,
        target_level: str = "B1",
    ) -> Optional[Dict]:
        """
        Translate an article into target_language, then simplify it to target_level.

        Two steps: a full translation (see translate), then the level simplifier
        that same-language articles get (simplify_text). One prompt that did both
        reached A1 by dropping facts and missed B1. Measured 2026-10-31 on 16
        uploads in 8 languages, A1 and B1, judged blind by Claude Opus 5.5: level
        fit went from 3.7 to 4.3 (B1 from 2.8 to 4.7), faithfulness from 3.4 to
        4.1, and the paragraphs and headings of every page were kept. DeepL then
        simplify ranked first most often, ahead of DeepSeek then simplify. Data
        and scripts: zeeguu-experiments, simplification/2026-10-30-markdown-input.

        content may be Markdown (an upload's page) or plain text with paragraphs
        separated by blank lines.

        Returns: Dict with 'title', 'content' (HTML), 'summary' and 'model_name'
        (the model that simplified it), or None if failed
        """
        translated = self.translate(title, content, source_language, target_language)
        if not translated:
            return None
        return self.simplify_text(translated["title"], translated["content"], target_level, target_language)

    def translate(self, title: str, content: str, source_language: str, target_language: str) -> Optional[Dict]:
        """
        A complete, faithful translation of an article, its structure kept.

        DeepL first: in the 2026-10-31 measurement it was as good a start for the
        simplifier as DeepSeek and took 1s instead of 6. The LLMs are the fallback
        (no key, a language DeepL lacks, its monthly quota). Every translation is
        checked for language: "left it in the source language" is the likeliest
        way for it to go wrong. An LLM is asked again once, then the next
        provider is tried.

        Returns: Dict with 'title' and 'content' (Markdown), or None if failed
        """
        target_name = Language.LANGUAGE_NAMES.get(target_language, target_language)
        context = f"{target_name} translation of '{title[:50]}'"

        translated = deepl_translate_article(title, content, target_language)
        if translated:
            try:
                return generate_in_language(lambda _: translated, target_language, _text_fields, context, attempts=1)
            except LanguageMismatchError as e:
                log(f"DeepL did not translate into {target_name}: {e}")

        source_name = Language.LANGUAGE_NAMES.get(source_language, source_language)
        prompt = _translation_prompt(title, content, source_name, target_name)
        providers = [
            ("DeepSeek", self.deepseek_api_key, self._complete_deepseek),
            ("Anthropic", self.anthropic_api_key, self._complete_haiku),
        ]
        for provider, api_key, complete in providers:
            if not api_key:
                continue
            log(f"Using {provider} to translate from {source_language} to {target_language}")

            def generate(correction):
                reply = complete(prompt + correction, TRANSLATION_MAX_TOKENS, TRANSLATION_TIMEOUT)
                if not reply:
                    raise Exception(f"{provider} returned no translation")
                return parse_translation_reply(reply)

            try:
                return generate_in_language(generate, target_language, _text_fields, context)
            except LanguageMismatchError as e:
                log(f"{provider} did not translate into {target_name}: {e}")
            except Exception as e:
                log(f"{provider} translation failed: {e}")

        log("No translation provider succeeded (or none is configured)")
        return None

    def _assess_cefr_anthropic(
        self, title: str, content: str, language_code: str
    ) -> Optional[str]:
        """Assess CEFR level using Anthropic"""
        language_name = Language.LANGUAGE_NAMES.get(language_code, language_code)

        prompt = f"""Assess the CEFR level and identify the main topic of this {language_name} article.

Title: {title}
Content: {content[:2000]}...

Consider for CEFR level:
- Vocabulary level (basic vs advanced words)
- Sentence complexity (length, subordinate clauses)
- Abstract concepts vs concrete topics
- Technical terminology usage

Topics to choose from (select the most appropriate one):
- Sports
- Culture & Art
- Technology & Science
- Travel & Tourism
- Health & Society
- Business
- Politics
- Satire

Respond in this exact format:
CEFR: [level]
TOPIC: [topic]

Example response:
CEFR: B2
TOPIC: Business"""

        raw = haiku_completion(prompt, max_tokens=30, temperature=0.1)
        if not raw:
            return None
        result = raw.strip()

        cefr_level = None
        topic = None
        for line in result.split("\n"):
            if line.startswith("CEFR:"):
                cefr_level = line.replace("CEFR:", "").strip()
            elif line.startswith("TOPIC:"):
                topic = line.replace("TOPIC:", "").strip()

        cefr_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
        if cefr_level not in cefr_levels:
            # Last-ditch: grep the level out of unstructured output before giving up.
            for level in cefr_levels:
                if level in result.upper():
                    cefr_level = level
                    break
            if cefr_level not in cefr_levels:
                log(f"Could not extract valid CEFR level from Anthropic response: {result}")
                return None

        return (cefr_level, topic)

    def _assess_cefr_deepseek(
        self, title: str, content: str, language_code: str
    ) -> str:
        """Assess CEFR level using DeepSeek"""
        language_name = Language.LANGUAGE_NAMES.get(language_code, language_code)

        prompt = f"""You are a language learning expert. Assess the CEFR difficulty level and identify the main topic of this {language_name} article.

CEFR Level Guidelines:
- A1: Very basic vocabulary (1000 most common words), simple present tense, basic sentence structures
- A2: Expanded vocabulary (2000 words), past/future tenses, simple connectors  
- B1: Intermediate vocabulary (3000 words), complex sentences, opinion expressions
- B2: Advanced vocabulary, subjunctive mood, nuanced expressions
- C1: Sophisticated vocabulary, complex grammar, idiomatic expressions
- C2: Near-native level, literary devices, specialized terminology

Topics to choose from (select the most appropriate one):
- Sports
- Culture & Art
- Technology & Science
- Travel & Tourism
- Health & Society
- Business
- Politics
- Satire

IMPORTANT: If the article appears to be incomplete due to a paywall, respond with: "INCOMPLETE"

Analyze this {language_name} article:

Title: {title}
Content: {content[:2000]}...

Respond in this exact format:
CEFR: [level]
TOPIC: [topic]"""

        try:
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": models.DEEPSEEK_GENERAL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": models.output_tokens(models.DEEPSEEK_GENERAL, 30),
                    "temperature": 0.1,
                },
                timeout=30,
            )

            if response.status_code != 200:
                log(f"DeepSeek API error for CEFR assessment: {response.status_code}")
                return (None, None)

            result = response.json()["choices"][0]["message"]["content"].strip()

            if result == "INCOMPLETE":
                log("Article appears to be incomplete due to paywall")
                return (None, None)

            # Parse the response to extract CEFR and topic
            lines = result.split('\n')
            cefr_level = None
            topic = None
            
            for line in lines:
                if line.startswith("CEFR:"):
                    cefr_level = line.replace("CEFR:", "").strip()
                elif line.startswith("TOPIC:"):
                    topic = line.replace("TOPIC:", "").strip()
            
            # Validate CEFR level
            valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
            if cefr_level not in valid_levels:
                # Fallback: try to extract from anywhere in the response
                for level in valid_levels:
                    if level in result.upper():
                        cefr_level = level
                        break
                if cefr_level not in valid_levels:
                    # Can't parse response - return None
                    log(f"Could not extract valid CEFR level from DeepSeek response: {result}")
                    return (None, None)
            
            log(f"Successfully assessed CEFR level: {cefr_level}, Topic: {topic}")
            return (cefr_level, topic)

        except Exception as e:
            log(f"Error in DeepSeek CEFR assessment: {e}")
            return (None, None)

# Factory function for convenience
def get_simplification_service() -> SimplificationService:
    """Get a simplification service instance"""
    return SimplificationService()

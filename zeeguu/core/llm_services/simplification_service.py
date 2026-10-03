"""
Text simplification service using LLM providers (Anthropic and DeepSeek, each the other's fallback)
"""

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
from zeeguu.core.llm_services.prompts.level_simplification import (
    get_level_simplification_prompt,
    paragraphs,
)

# A whole article rewritten at one level, in one reply. A ~550-word article takes
# 8-13s with either provider; the learner waits, and a wrong-language reply is asked
# again before the next provider is tried, so the timeout bounds that wait 4 times over.
LEVEL_MAX_TOKENS = 8000
LEVEL_TIMEOUT = 60


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

    Returns None when nothing decodable is in there.
    """
    import json

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
    A guard for the title, applied at every level and by both providers.

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

    def _complete_deepseek(self, prompt: str) -> str:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.deepseek_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": models.DEEPSEEK_GENERAL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": LEVEL_MAX_TOKENS,
                "temperature": 0.1,
            },
            timeout=LEVEL_TIMEOUT,
        )
        if response.status_code != 200:
            raise Exception(f"DeepSeek API error: {response.status_code} - {response.text[:200]}")
        choice = response.json()["choices"][0]
        if choice.get("finish_reason") == "length":
            raise Exception(f"DeepSeek output truncated at max_tokens={LEVEL_MAX_TOKENS}")
        return (choice["message"]["content"] or "").strip()

    def _complete_haiku(self, prompt: str) -> Optional[str]:
        # None on API errors and on a reply cut off at max_tokens
        return haiku_completion(
            prompt, max_tokens=LEVEL_MAX_TOKENS, temperature=0.1, timeout=LEVEL_TIMEOUT
        )

    def translate_and_adapt(
        self,
        title: str,
        content: str,
        source_language: str,
        target_language: str,
        target_level: str = "B1",
    ) -> Optional[Dict]:
        """
        Translate and adapt text to target language and reading level.

        The riskiest LLM call in the codebase for output language: this is a
        translation task, so "left it in the source language" is the single most
        likely way for it to go wrong, and the result is stored as an article in
        the recipient's language. Checked against target_language, re-requested
        once, then abandoned (None) rather than stored untranslated.

        Returns: Dict with 'title', 'content', 'summary' keys or None if failed
        """
        # Map language codes to names
        language_names = {
            "ro": "Romanian",
            "en": "English",
            "de": "German",
            "es": "Spanish",
            "fr": "French",
            "nl": "Dutch",
            "it": "Italian",
            "da": "Danish",
            "pl": "Polish",
            "sv": "Swedish",
            "ru": "Russian",
            "no": "Norwegian",
            "hu": "Hungarian",
            "pt": "Portuguese",
        }
        
        source_lang_name = language_names.get(source_language, source_language)
        target_lang_name = language_names.get(target_language, target_language)
        
        context = f"{target_lang_name} translation of '{title[:50]}'"

        def translated_by(translate):
            """Wrap one provider's translate call for the output-language check."""

            def generate(correction):
                result = translate(correction)
                if not result:
                    raise Exception("translation returned nothing")
                return result

            return generate_in_language(generate, target_language, _text_fields, context)

        # Try DeepSeek first. Measured 2026-09-08 on ro->da A1: Haiku carried the
        # Romanian negation `Nu` through untranslated (it is also a Danish word,
        # meaning "now"), inverting the headline's claim -- 0/5 runs correct,
        # against 3/4 for DeepSeek. Cross-checked on da->fr, where DeepSeek was
        # also more faithful (it kept the article's subject in the title, which
        # Haiku dropped under A1 pressure) and ~30% faster (6.0s vs 8.5s median).
        # Anthropic stays as the fallback below, which also keeps this path
        # working when the Anthropic monthly cap is hit.
        if self.deepseek_api_key:
            log(f"Using DeepSeek for translation from {source_language} to {target_language} at {target_level}")
            try:
                return translated_by(
                    lambda correction: self._translate_and_adapt_deepseek(
                        title, content, source_lang_name, target_lang_name, target_level, correction
                    )
                )
            except LanguageMismatchError as e:
                log(f"DeepSeek did not translate into {target_lang_name}, trying Anthropic: {e}")
            except Exception as e:
                log(f"DeepSeek translation failed, falling back to Anthropic: {e}")

        # Fallback to Anthropic
        if self.anthropic_api_key:
            log(f"Using Anthropic for translation from {source_language} to {target_language} at {target_level}")
            try:
                return translated_by(
                    lambda correction: self._translate_and_adapt_anthropic(
                        title, content, source_lang_name, target_lang_name, target_level, correction
                    )
                )
            except LanguageMismatchError as e:
                log(f"Anthropic did not translate into {target_lang_name}, giving up: {e}")
            except Exception as e:
                log(f"Anthropic translation failed: {e}")

        log("Neither ANTHROPIC_TEXT_SIMPLIFICATION_KEY nor DEEPSEEK_API_KEY configured")
        return None

    def _get_level_specific_prompt(self, target_level: str, source_language: str, target_language: str) -> str:
        """Get CEFR level-specific prompt for translation and adaptation"""
        
        log(f"_get_level_specific_prompt called with: target_level={target_level}, source_language={source_language}, target_language={target_language}")
        
        if target_level == "A1":
            return f"""Then, dramatically simplify the translation to A1 CEFR level using these EXTREME A1 CONSTRAINTS:

🚨🚨🚨 CRITICAL: YOU MUST WRITE IN {target_language.upper()} ONLY! NOT ENGLISH! 🚨🚨🚨
🚨 IF YOU USE COMPLEX WORDS YOU HAVE COMPLETELY FAILED! 🚨
🚨 IF YOU WRITE IN ENGLISH INSTEAD OF {target_language.upper()}, YOU HAVE FAILED! 🚨
🚨 DO NOT SHORTEN THE ARTICLE - KEEP ALL CONTENT! 🚨

ULTRA-STRICT A1 RULES:
• WORD LIMIT: Maximum 5 words per sentence. COUNT EACH WORD!
• VOCABULARY: ONLY words a 5-year-old child knows. NO EXCEPTIONS!
• WORD LENGTH: If a word has more than 6 letters, DON'T USE IT
• NO abstract concepts → use concrete simple words
• NO technical terms → explain with basic words  
• NO complex verbs → use: is, go, see, say, have, want, like
• NO compound words → break into simple parts
• Write like a children's picture book
• Group 2-3 short sentences per paragraph
• PRESERVE ALL CONTENT: Every example, every point, every section from the original must be included
• You may need MORE sentences to express complex ideas simply - that's OK!

USE ONLY THE MOST BASIC WORDS IN {target_language}:
- Basic pronouns (I, you, he, she, it, they)
- Simple verbs (is, go, see, say, have, want, like, eat, drink, work, play)
- Simple nouns (man, woman, child, people, house, car, money, time, day)
- Simple adjectives (good, bad, big, small, happy, sad, new, old)

TRANSFORMATION PRINCIPLE:
❌ WRONG: Complex sentences with advanced vocabulary
✅ CORRECT: Very short sentences. Simple words only. Like a children's book.

CRITICAL TEST: If a 5-year-old child learning {target_language} cannot understand EVERY single word, you have COMPLETELY FAILED A1!

🔥 FINAL WARNING: Write ONLY in {target_language.upper()}! NO English words allowed! 🔥"""

        elif target_level == "A2":
            return f"""Then, simplify the translation to A2 CEFR level:

A2 LEVEL GUIDELINES:
• Simple vocabulary (first 2000 most common words)
• Maximum 12 words per sentence
• Simple tenses: present, past, future (will)
• Basic connectors: and, but, because, when, if
• Clear subject-verb-object structure
• Avoid complex grammar and abstract concepts
• Group 3-4 sentences per paragraph

Write like a simple news article for language learners."""

        elif target_level in ["B1", "B2"]:
            return f"""Then, adapt the translation to {target_level} CEFR level:

{target_level} LEVEL GUIDELINES:
• Intermediate vocabulary and expressions
• Varied sentence length (8-20 words)
• Mix of simple and complex tenses
• Connectors: however, although, despite, therefore
• Some passive voice and conditionals allowed
• Clear paragraph structure with topic sentences
• Explain complex concepts but keep accessible

Write like a mainstream news article that's clear and engaging."""

        else:  # C1, C2
            return f"""Then, adapt the translation to {target_level} CEFR level:

{target_level} LEVEL GUIDELINES:
• Advanced vocabulary and sophisticated expressions
• Complex sentence structures and varied length
• Full range of tenses and grammatical structures
• Advanced connectors and discourse markers
• Nuanced language and abstract concepts
• Maintain original complexity and style
• Professional/academic writing style

Focus on accurate translation while maintaining natural, fluent {target_language}."""

    def _assess_cefr_anthropic(
        self, title: str, content: str, language_code: str
    ) -> Optional[str]:
        """Assess CEFR level using Anthropic"""
        language_names = {
            "ro": "Romanian",
            "en": "English",
            "fr": "French",
            "es": "Spanish",
            "de": "German",
            "da": "Danish",
            "nl": "Dutch",
            "it": "Italian",
            "pt": "Portuguese",
            "sv": "Swedish",
            "no": "Norwegian",
            "fi": "Finnish",
        }

        language_name = language_names.get(language_code, "Romanian")

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
        language_names = {
            "da": "Danish",
            "es": "Spanish",
            "en": "English",
            "de": "German",
            "fr": "French",
            "nl": "Dutch",
            "it": "Italian",
            "pt": "Portuguese",
            "ro": "Romanian",
        }

        language_name = language_names.get(language_code, language_code)

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
                    "max_tokens": 30,
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
                if not cefr_level:
                    # Can't parse response - return None
                    log(f"Could not extract valid CEFR level from DeepSeek response: {result}")
                    return (None, None)
            
            log(f"Successfully assessed CEFR level: {cefr_level}, Topic: {topic}")
            return (cefr_level, topic)

        except Exception as e:
            log(f"Error in DeepSeek CEFR assessment: {e}")
            return (None, None)

    def _translate_and_adapt_anthropic(
        self, title: str, content: str, source_language: str, target_language: str,
        target_level: str, correction: str = ""
    ) -> Optional[Dict]:
        """Translate and adapt text using Anthropic"""
        
        import re
        import unicodedata
        
        # Clean content to remove invalid control characters
        def clean_text(text):
            # Much more aggressive cleaning
            # Keep only printable ASCII, basic unicode letters/numbers, and whitespace
            import string
            allowed_chars = string.printable + 'àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿĀāĂăĄąĆćĈĉĊċČčĎďĐđĒēĔĕĖėĘęĚěĜĝĞğĠġĢģĤĥĦħĨĩĪīĬĭĮįİıĲĳĴĵĶķĸĹĺĻļĽľĿŀŁłŃńŅņŇňŉŊŋŌōŎŏŐőŒœŔŕŖŗŘřŚśŜŝŞşŠšŢţŤťŦŧŨũŪūŬŭŮůŰűŲųŴŵŶŷŸŹźŻżŽž'
            cleaned = ''.join(char for char in text if char in allowed_chars or char.isalnum() or char.isspace())
            # Replace multiple whitespace with single space
            cleaned = re.sub(r'\s+', ' ', cleaned)
            return cleaned.strip()
        
        title = clean_text(title)
        content = clean_text(content)
        
        log(f"Input content length: {len(content)} chars")
        log(f"Input title: {title}")
        
        # Get level-specific prompt
        log(f"Anthropic: Calling _get_level_specific_prompt with target_level={target_level}, source_language={source_language}, target_language={target_language}")
        level_prompt = self._get_level_specific_prompt(target_level, source_language, target_language)
        title_rule = _title_rule(source_language, target_language)
        
        prompt = f"""You must complete this task in TWO CLEAR STEPS. Do both steps
in your head and output ONLY the STEP 2 result: one JSON object, nothing before
or after it — no step headings, no code fences, and NOT the STEP 1 translation.

STEP 1: First, translate this {source_language} article to {target_language} accurately and completely. PRESERVE ALL CONTENT AND EXAMPLES.

STEP 2: {level_prompt}

{title_rule}

CRITICAL: Do NOT shorten or summarize the article. Keep ALL the content, examples, and points from the original. Only simplify the LANGUAGE and VOCABULARY, not the length or content.

⚠️ IMPORTANT: The translated output should be approximately the SAME LENGTH as the original. If the original has 20 paragraphs, your translation should also have around 20 paragraphs. DO NOT SKIP ANY SECTIONS!

FORMATTING REQUIREMENTS:
- Return content in clean Markdown format
- Use proper Markdown syntax: ## for headings, **bold**, *italics*, > for quotes
- Separate paragraphs with double newlines
- Use - or * for bullet points, 1. 2. 3. for numbered lists
- Preserve structure and formatting from the original
- No HTML tags - use Markdown only

Translate and adapt this article:

Title: {title}
Content: {content}

Provide the response in this exact JSON format (escape quotes properly):
{{
  "title": "translated and adapted title",
  "content": "## Main Topic\n\nFirst paragraph with **important term** highlighted.\n\nSecond paragraph with *emphasis* and more details.\n\n- Bullet point one\n- Bullet point two\n\nThird paragraph with conclusion.",
  "summary": "First sentence of summary. Second sentence with key point. Third sentence with conclusion."
}}

IMPORTANT: 
- Escape any quotes in the content using \\"
- Use proper HTML paragraph tags for content
- Summary should be concise, maximum 25 words, using {target_level} vocabulary
- Ensure valid JSON format"""

        prompt += correction

        log(f"Prompt length: {len(prompt)} chars")

        # Route through the shared Haiku client so the model (models.SIMPLIFICATION,
        # via haiku_client), key, endpoint, and truncation handling live in one
        # place instead of a second hand-rolled copy here.
        #
        # max_tokens must leave room for the *translated* output, which for a full
        # chapter runs at least as long as the input (German et al. run 20-30%
        # longer). Haiku 4.5's ceiling is 64k, so 16k comfortably covers a single
        # chapter (~4k words). If the model still hits the cap, haiku_completion
        # returns None (it treats stop_reason "max_tokens" as a failure) rather
        # than handing back truncated, unparseable JSON.
        result_text = haiku_completion(
            prompt, max_tokens=16000, temperature=0.3, timeout=120
        )
        if not result_text:
            return None

        try:
            import json
            import markdown2

            result = parse_llm_json(result_text)
            if not result:
                log("No JSON object in the Anthropic reply")
                log(f"Problematic JSON response: {result_text}")
                return None

            if "content" in result and result["content"]:
                result["content"] = markdown2.markdown(
                    result["content"],
                    extras=['break-on-newline', 'fenced-code-blocks', 'tables']
                )

            if "summary" not in result or not result["summary"]:
                from bs4 import BeautifulSoup
                clean_content = BeautifulSoup(result["content"], 'html.parser').get_text()
                result["summary"] = clean_content[:200] + "..."
            return result
        except json.JSONDecodeError as e:
            log(f"Error parsing Anthropic JSON: {e}")
            log(f"Problematic JSON response: {result_text}")
            return None
        except Exception as e:
            log(f"Error in Anthropic translation: {e}")
            return None

    def _translate_and_adapt_deepseek(
        self, title: str, content: str, source_language: str, target_language: str,
        target_level: str, correction: str = ""
    ) -> Optional[Dict]:
        """Translate and adapt text using DeepSeek"""
        
        # Get level-specific prompt
        level_prompt = self._get_level_specific_prompt(target_level, source_language, target_language)
        title_rule = _title_rule(source_language, target_language)
        
        prompt = f"""You must complete this task in TWO CLEAR STEPS. Do both steps
in your head and output ONLY the STEP 2 result: one JSON object, nothing before
or after it — no step headings, no code fences, and NOT the STEP 1 translation.

STEP 1: First, translate this {source_language} article to {target_language} accurately and completely. PRESERVE ALL CONTENT AND EXAMPLES.

STEP 2: {level_prompt}

{title_rule}

CRITICAL: Do NOT shorten or summarize the article. Keep ALL the content, examples, and points from the original. Only simplify the LANGUAGE and VOCABULARY, not the length or content.

⚠️ IMPORTANT: The translated output should be approximately the SAME LENGTH as the original. If the original has 20 paragraphs, your translation should also have around 20 paragraphs. DO NOT SKIP ANY SECTIONS!

FORMATTING REQUIREMENTS:
- Return content in clean Markdown format
- Use proper Markdown syntax: ## for headings, **bold**, *italics*, > for quotes
- Separate paragraphs with double newlines
- Use - or * for bullet points, 1. 2. 3. for numbered lists
- Preserve structure and formatting from the original
- No HTML tags - use Markdown only

Article to translate:
Title: {title}
Content: {content}

Return ONLY valid JSON in this exact format (no markdown, no code blocks):
{{
  "title": "translated title",
  "content": "## Main Topic\n\nFirst paragraph with **important term** highlighted.\n\nSecond paragraph with *emphasis* and more details.\n\n- Bullet point one\n- Bullet point two\n\nThird paragraph with conclusion.",
  "summary": "First sentence of summary. Second sentence with key point. Third sentence with conclusion."
}}

IMPORTANT: Summary should be concise, maximum 25 words, using {target_level} vocabulary."""

        prompt += correction

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
                    # deepseek-chat caps max_tokens at 8192 (unlike Haiku's 64k);
                    # requesting more is rejected with a 400. 8192 is the most
                    # headroom available — anything longer is caught by the
                    # finish_reason check below rather than truncated silently.
                    "max_tokens": 8192,
                    "temperature": 0.3,
                },
                timeout=120,
            )

            if response.status_code == 200:
                try:
                    response_data = response.json()
                    choice = response_data["choices"][0]
                    result_text = choice["message"]["content"]
                    log(f"DeepSeek raw response: {result_text[:200]}...")

                    # finish_reason "length" is DeepSeek's truncation signal (the
                    # equivalent of Anthropic's stop_reason "max_tokens"). Bail
                    # rather than parse a cut-off response.
                    if choice.get("finish_reason") == "length":
                        log(
                            f"DeepSeek translation hit the token cap "
                            f"(finish_reason=length, input {len(content)} chars)"
                        )
                        return None

                    import json
                    import markdown2

                    result = parse_llm_json(result_text)
                    if not result:
                        log("No JSON object in the DeepSeek reply")
                        log(f"Raw response: {result_text}")
                        return None
                    
                    # Convert markdown content to HTML
                    if "content" in result and result["content"]:
                        result["content"] = markdown2.markdown(
                            result["content"],
                            extras=['break-on-newline', 'fenced-code-blocks', 'tables']
                        )
                    
                    # Add fallback summary if not provided by LLM
                    if "summary" not in result or not result["summary"]:
                        from bs4 import BeautifulSoup
                        clean_content = BeautifulSoup(result["content"], 'html.parser').get_text()
                        result["summary"] = clean_content[:200] + "..."
                    return result
                except json.JSONDecodeError as e:
                    log(f"Failed to parse DeepSeek JSON response: {e}")
                    log(f"Raw response: {result_text}")
                    return None
                except Exception as e:
                    log(f"Error processing DeepSeek response: {e}")
                    return None
            else:
                log(f"DeepSeek API error: {response.status_code}")
                log(f"Response text: {response.text}")
                return None

        except Exception as e:
            log(f"Error in DeepSeek translation: {e}")
            return None


# Factory function for convenience
def get_simplification_service() -> SimplificationService:
    """Get a simplification service instance"""
    return SimplificationService()

"""
Article simplification and content classification.

This module handles:
- Creating CEFR-level appropriate simplified versions of articles
- Classifying content (disturbing news, etc.)

Split pipeline: one LLM call assesses the article (paywall/advertorial check, disturbing content,
article type, CEFR level, summary), then one call per simpler level writes that version, in parallel.
DeepSeek is the default provider; every call falls back to Anthropic (Haiku) if DeepSeek fails.
See prompts/split_simplification.py for the prompts and the evaluation behind them.
"""

import copy
import os
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from zeeguu.logging import log
from zeeguu.core.model.article import Article
from zeeguu.core.model.url import Url
from .haiku_client import HAIKU_MODEL, haiku_completion_or_raise
from .prompts.split_simplification import (
    get_split_assessment_prompt,
    get_split_level_prompt,
    paragraphs,
)
from zeeguu.core.llm_services import models


CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
PROVIDERS = ("deepseek", "anthropic")
MODEL_NAMES = {"deepseek": models.DEEPSEEK_GENERAL, "anthropic": HAIKU_MODEL}

ASSESSMENT_MAX_TOKENS = 2000
LEVEL_MAX_TOKENS = 8000
LLM_TIMEOUT = 180

# first word of an assessment that rejects the article -> exception message
REJECTIONS = {
    "unfinished": "PAYWALL: Article appears to be incomplete due to paywall",
    "advertorial": "ADVERTORIAL: Article appears to be advertorial/promotional content",
}

def get_target_levels_for_original_level(original_level: str) -> list[str]:
    """
    Get the list of CEFR levels that should be created for an original article level.
    Returns all levels simpler than the original level.

    Args:
        original_level: The assessed CEFR level of the original article

    Returns:
        List of CEFR levels to create simplified versions for
    """
    # CEFR levels in order from simplest to most complex
    cefr_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]

    if original_level not in cefr_levels:
        # If invalid or unknown level, default to creating A1 and A2
        log(f"Unknown original CEFR level '{original_level}', defaulting to A1 and A2")
        return ["A1", "A2"]

    # Find the index of the original level
    original_index = cefr_levels.index(original_level)

    # Return all levels simpler than the original
    target_levels = cefr_levels[:original_index]

    if not target_levels:
        # If original is already A1, no simpler versions needed
        log(
            f"Original article is already at {original_level} level, no simpler versions needed"
        )
        return []

    log(
        f"Original article is {original_level} level, creating simplified versions for: {target_levels}"
    )
    return target_levels



def _deepseek_completion(prompt: str, max_tokens: int) -> str:
    api_key = os.environ.get("DEEPSEEK_API_SIMPLIFICATIONS")
    if not api_key:
        raise Exception("DEEPSEEK_API_SIMPLIFICATIONS not set")
    response = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": models.DEEPSEEK_GENERAL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.1,
        },
        timeout=LLM_TIMEOUT,
    )
    if response.status_code != 200:
        raise Exception(f"DeepSeek API error: {response.status_code} - {response.text[:200]}")
    choice = response.json()["choices"][0]
    if choice.get("finish_reason") == "length":
        raise Exception(f"DeepSeek output truncated at max_tokens={max_tokens}")
    return choice["message"]["content"].strip()


def _complete(provider: str, prompt: str, max_tokens: int) -> str:
    if provider == "deepseek":
        return _deepseek_completion(prompt, max_tokens)
    return haiku_completion_or_raise(
        prompt,
        max_tokens=max_tokens,
        temperature=0.1,
        timeout=LLM_TIMEOUT,
        raise_on_truncation=True,
    ).strip()


def _with_fallback(preferred: str, what: str, attempt):
    """
    Call attempt(provider) with the preferred provider, then with the other one.
    attempt raises on API errors and on responses it can't parse.
    Returns (provider, result).
    """
    errors = []
    for provider in (preferred, *[p for p in PROVIDERS if p != preferred]):
        try:
            return provider, attempt(provider)
        except Exception as e:
            log(f"  {what}: {provider} failed: {e}")
            errors.append(f"{provider}: {e}")
    raise Exception(f"{what} failed with all providers ({'; '.join(errors)})")


def _clean(text: str) -> str:
    return text.strip().strip("[](){}\"'")


def _strip_markdown(text: str) -> str:
    """Remove markdown bold/italic formatting (summaries are plain text)."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)
    return text


def _parse_fields(text: str, names: tuple, last: str = None) -> dict:
    """
    Parse 'NAME: value' sections (values may span lines). Once the `last` section starts,
    everything after it belongs to it.
    """
    fields, current = {}, None
    pattern = re.compile(rf"^\W*({'|'.join(names)})\W*:\s*(.*)$")
    for line in text.splitlines():
        if last is not None and current == last:
            fields[current].append(line)
            continue
        match = pattern.match(line.strip())
        if match:
            current = match.group(1)
            fields[current] = [match.group(2)]
        elif last is not None and re.match(r"^\s*\[\d+\]", line):
            # models sometimes skip the CONTENT: line and start with the numbered paragraphs
            current = last
            fields[current] = [line]
        elif current:
            fields[current].append(line)
    return {k: "\n".join(v).strip() for k, v in fields.items()}


def _parse_assessment(text: str) -> dict:
    first_word = re.sub(r"[^a-z]", "", text.strip().split("\n")[0].lower()) if text.strip() else ""
    if first_word in REJECTIONS:
        return {"rejected": first_word}

    fields = _parse_fields(
        text, ("DISTURBING_CONTENT", "ARTICLE_TYPE", "ORIGINAL_LEVEL", "ORIGINAL_SUMMARY")
    )
    summary = _strip_markdown(_clean(fields.get("ORIGINAL_SUMMARY", "")))
    if not summary:
        raise Exception("Missing original summary in assessment")

    original_level = _clean(fields.get("ORIGINAL_LEVEL", "")).upper()
    if original_level not in CEFR_LEVELS:
        log(f"Warning: Invalid original CEFR level '{original_level}', defaulting to 'B2'")
        original_level = "B2"

    article_type = _clean(fields.get("ARTICLE_TYPE", "")).upper()
    return {
        "is_disturbing": _clean(fields.get("DISTURBING_CONTENT", "NO")).upper() == "YES",
        "article_type": article_type.lower() if article_type in ("NEWS", "GENERAL") else None,
        "original_cefr_level": original_level,
        "original_summary": summary,
    }


def _parse_level(text: str, expected_paragraphs: int) -> dict:
    """TITLE: / SUMMARY: / CONTENT: with [n]-numbered paragraphs -> {title, content, summary}."""
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


def simplify_article_adaptive_levels(
    title: str,
    content: str,
    target_language: str,
    simplification_provider: str = None,
    correct_grammar: bool = False,
) -> dict:
    """
    Assess the article and simplify it to all levels simpler than the original.

    One call for the assessment, then one call per level (in parallel). Every call uses the
    preferred provider and falls back to the other one.

    Args:
        title: Original article title
        content: Original article content
        target_language: Language code (e.g., 'da', 'es')
        simplification_provider: Preferred provider, 'deepseek' (default) or 'anthropic'
        correct_grammar: Whether to run a separate Haiku grammar/spelling correction pass after simplification. Default is False — the DeepSeek + Haiku correction experiment ran 2025-12-09 → 2026-04-05 and concluded that the corrections were overwhelmingly cosmetic (~96% of title fixes and ~72% of content fixes were ≤2 char diffs). The correction pass and grammar_correction_log writes are kept in place but disabled by default; data from the experiment is preserved in the table.

    Returns:
        Dict containing all simplified versions and original metadata:
        {
            'is_disturbing': bool,
            'article_type': 'news', 'general' or None,
            'original_cefr_level': str,
            'original_summary': str,
            'simplified_levels': list[str],  # e.g., ['A1', 'A2', 'B1']
            'versions': {
                'A1': {'title': str, 'content': str, 'summary': str, 'model_name': str},
                ...
            },
            'uncorrected_versions': dict or None,
            'provider': str,  # provider that wrote the (first) versions
            'model_name': str  # its model, e.g. 'deepseek-chat'
        }

    Raises:
        Exception: If the article is rejected (paywall, advertorial) or no version could be created
    """
    preferred = simplification_provider or "deepseek"
    if preferred not in PROVIDERS:
        raise ValueError(f"Unknown simplification provider: {preferred}")

    try:
        log(f"Simplifying article '{title[:50]}...' in {target_language}")
        log(f"  Article length: {len(content)} characters, preferred provider: {preferred}")

        assessment_prompt = get_split_assessment_prompt(target_language, title, content)
        provider, assessment = _with_fallback(
            preferred,
            "Assessment",
            lambda p: _parse_assessment(_complete(p, assessment_prompt, ASSESSMENT_MAX_TOKENS)),
        )
        if "rejected" in assessment:
            raise Exception(REJECTIONS[assessment["rejected"]])

        original_level = assessment["original_cefr_level"]
        target_levels = get_target_levels_for_original_level(original_level)
        expected_paragraphs = len(paragraphs(content))

        def simplify(level):
            def attempt(p):
                # the strict prompt (hard limits + words to avoid) only helps DeepSeek; with Haiku it hurt faithfulness
                prompt = get_split_level_prompt(
                    target_language, title, content, level, strict=p == "deepseek"
                )
                return _parse_level(_complete(p, prompt, LEVEL_MAX_TOKENS), expected_paragraphs)

            try:
                level_provider, version = _with_fallback(preferred, f"{level} version", attempt)
                version["model_name"] = MODEL_NAMES[level_provider]
                return level, version
            except Exception as e:
                log(f"  Warning: skipping {level}: {e}")
                return level, None

        with ThreadPoolExecutor(max_workers=max(1, len(target_levels))) as pool:
            results = list(pool.map(simplify, target_levels))
        versions = {level: version for level, version in results if version}
        simplified_levels = [level for level in target_levels if level in versions]

        if target_levels and not simplified_levels:
            raise Exception(f"No simplified versions were created for levels {target_levels}")
        log(
            f"Simplified article to {simplified_levels} (original {original_level}, "
            f"disturbing: {assessment['is_disturbing']})"
        )

        # Grammar correction pass - fix spelling/grammar errors introduced during simplification
        uncorrected_versions = None
        if correct_grammar and simplified_levels:
            log(
                f"  Running grammar correction pass on {len(simplified_levels)} simplified versions..."
            )
            try:
                from .grammar_correction_service import get_grammar_correction_service

                grammar_service = get_grammar_correction_service()

                # Keep a copy of uncorrected versions for logging
                uncorrected_versions = copy.deepcopy(versions)

                for level in simplified_levels:
                    log(f"    Correcting {level} version...")
                    model_name = versions[level]["model_name"]
                    versions[level] = grammar_service.correct_simplified_version(
                        versions[level], target_language, provider="anthropic"
                    )
                    versions[level]["model_name"] = model_name
                    log(f"    {level} version corrected")

                log(f"  Grammar correction completed for all levels")
            except Exception as e:
                # Log but don't fail - uncorrected simplification is better than no simplification
                log(
                    f"  WARNING: Grammar correction failed, using uncorrected versions: {e}"
                )
                uncorrected_versions = None  # Don't log if correction failed

        model_name = (
            versions[simplified_levels[0]]["model_name"] if simplified_levels else MODEL_NAMES[provider]
        )
        return {
            **assessment,
            "simplified_levels": simplified_levels,
            "versions": versions,
            "uncorrected_versions": uncorrected_versions,  # For logging corrections
            "provider": next(p for p, m in MODEL_NAMES.items() if m == model_name),
            "model_name": model_name,
        }

    except Exception as e:
        log(f"  ERROR: {str(e)}")
        raise Exception(f"Failed to adaptively simplify article: {str(e)}")


def create_simplified_article_adaptive(
    session, original_article: Article, cefr_level: str, commit: bool = True
) -> Article:
    """
    Create a simplified version of an article using the adaptive approach.
    Uses the LLM to assess the original level and create the requested level.

    Args:
        session: Database session
        original_article: The original article to simplify
        cefr_level: Target CEFR level (A1, A2, B1, B2, C1, C2)
        commit: Whether to commit the transaction

    Returns:
        The created simplified article

    Raises:
        Exception: If simplification fails
    """

    # Check if simplified version already exists
    for existing in original_article.simplified_versions:
        if existing.cefr_level == cefr_level:
            log(
                f"Simplified version for {cefr_level} already exists for article {original_article.id}"
            )
            return existing

    # Get the content to simplify
    title = original_article.title
    content = original_article.get_content()
    language_code = original_article.language.code

    log(
        f"Creating {cefr_level} simplified version for article {original_article.id} using adaptive approach"
    )

    try:
        # Use the adaptive approach to get all levels
        result = simplify_article_adaptive_levels(title, content, language_code)

        # Extract the results
        original_level = result["original_cefr_level"]
        original_summary = result["original_summary"]
        simplified_levels = result["simplified_levels"]
        versions = result["versions"]
        provider = result["provider"]
        model_name = result["model_name"]

        # Check if the requested level is available
        if cefr_level not in versions:
            raise Exception(
                f"Requested level {cefr_level} was not created by the LLM. Available levels: {list(versions.keys())}"
            )

        # Update the original article with assessed metadata if not already set
        if not original_article.cefr_level:
            original_article.cefr_level = original_level
        if not original_article.summary:
            original_article.summary = original_summary

        # Create the simplified article
        version_data = versions[cefr_level]

        simplified_article = Article.create_simplified_version(
            session=session,
            parent_article=original_article,
            simplified_title=version_data["title"],
            simplified_content=version_data["content"],
            simplified_summary=version_data["summary"],
            cefr_level=cefr_level,
            ai_model=version_data.get("model_name", model_name),
            original_cefr_level=original_level,
            original_summary=original_summary,
            commit=commit,
        )

        log(f"Created simplified article {simplified_article.id} at {cefr_level} level")
        return simplified_article

    except Exception as e:
        raise Exception(f"Failed to create {cefr_level} simplified version: {str(e)}")


def simplify_and_classify(
    session, original_article: Article, simplification_provider: str = None
) -> tuple[list[Article], list[tuple[str, str]]]:
    """
    Simplify article to multiple CEFR levels and classify content type (e.g., disturbing).

    Uses simplify_article_adaptive_levels to:
    1. Assess the original article's CEFR level
    2. Create all appropriate simplified versions
    3. Detect content classifications (disturbing news, etc.)

    This function is designed to be called by the crawler/article creation process.

    Args:
        session: Database session
        original_article: The original article to simplify
        simplification_provider: Provider to use ('deepseek' or 'anthropic'), overrides default if set

    Returns:
        Tuple of (simplified_articles, classifications)
        - simplified_articles: List of created simplified Article objects
        - classifications: List of (classification_type, detection_method) tuples
          e.g., [("DISTURBING", "LLM")]
    """

    # Only create simplified versions for articles that don't already have them
    # and are not themselves simplified versions
    if original_article.parent_article_id:
        log(
            f"SKIP: Article {original_article.id} is already a simplified version (parent: {original_article.parent_article_id})"
        )
        return [], []

    if original_article.simplified_versions:
        existing_levels = [v.cefr_level for v in original_article.simplified_versions]
        log(
            f"SKIP: Article {original_article.id} already has {len(original_article.simplified_versions)} simplified versions: {existing_levels}"
        )
        return [], []

    # Only simplify articles with substantial content
    word_count = original_article.get_word_count()
    if word_count < 100:
        log(
            f"SKIP: Article {original_article.id} is too short for simplification - {word_count} words (minimum: 100 words)"
        )
        return [], []

    log(
        f"STARTING: Auto-creating simplified versions for article {original_article.id}"
    )
    log(f"  Title: {original_article.title[:100]}...")
    log(f"  Language: {original_article.language.code}")
    log(f"  Word count: {word_count}")

    try:
        # One call for the assessment, then one call per simplified level
        title = original_article.title
        content = original_article.get_content()
        language_code = original_article.language.code

        log(f"  Calling LLM for assessment and simplification...")
        log(
            f"  Request details: title_len={len(title)}, content_len={len(content)}, language={language_code}"
        )
        result = simplify_article_adaptive_levels(
            title,
            content,
            language_code,
            simplification_provider=simplification_provider,
        )
        log(f"  LLM call completed successfully")

        # Extract the results
        is_disturbing = result.get("is_disturbing", False)
        article_type = result.get("article_type")
        original_level = result["original_cefr_level"]
        original_summary = result["original_summary"]
        simplified_levels = result["simplified_levels"]
        versions = result["versions"]
        uncorrected_versions = result.get(
            "uncorrected_versions"
        )  # For logging corrections
        provider = result["provider"]
        model_name = result["model_name"]

        log(f"  LLM Assessment complete:")
        log(f"    Provider used: {provider.upper()} ({model_name})")
        log(f"    Original level: {original_level}")
        log(f"    Article type: {article_type}")
        log(f"    Simplified levels to create: {simplified_levels}")
        log(f"    Versions returned by LLM: {list(versions.keys())}")
        log(f"    Disturbing content detected: {is_disturbing}")

        # Update the original article with assessed metadata
        log(f"  Updating original article metadata...")
        original_article.cefr_level = original_level
        if article_type:
            original_article.article_type = article_type
        if not original_article.summary:
            original_article.summary = original_summary

        if not simplified_levels:
            log(
                f"SKIP: Article {original_article.id} is already at {original_level} level - no simpler versions needed (AI assessment)"
            )
            # committing before return
            session.commit()

            # Return classifications even if no simplification needed
            classifications = []
            if is_disturbing:
                classifications.append(("DISTURBING", "LLM"))
            return [], classifications

        # Create all simplified articles
        log(f"  Creating {len(simplified_levels)} simplified articles in database...")
        simplified_articles = []

        for level in simplified_levels:
            log(f"    Creating {level} version...")
            if level in versions:
                version_data = versions[level]
                simplified_article = Article.create_simplified_version(
                    session=session,
                    parent_article=original_article,
                    simplified_title=version_data["title"],
                    simplified_content=version_data["content"],
                    simplified_summary=version_data["summary"],
                    cefr_level=level,
                    ai_model=version_data.get("model_name", model_name),
                    original_cefr_level=None,  # Already set on parent
                    original_summary=None,  # Already set on parent
                    commit=False,
                )
                simplified_articles.append(simplified_article)
                log(f"    Created {level} version (temp ID, will commit later)")
            else:
                log(f"    Skipping {level} - not in versions data")

        # Commit all changes
        log(
            f"  Committing {len(simplified_articles)} simplified articles to database..."
        )
        session.commit()
        log(f"  Database commit completed")

        # Update URLs for all simplified articles now that they have IDs
        log(f"  Updating URLs for simplified articles...")
        for simplified_article in simplified_articles:
            log(
                f"    Updating URL for article {simplified_article.id} ({simplified_article.cefr_level})"
            )
            final_url_string = (
                f"https://zeeguu.org/read/article?id={simplified_article.id}"
            )
            final_url = Url.find_or_create(session, final_url_string)
            simplified_article.url = final_url
            session.add(simplified_article)

        # Commit URL updates
        log(f"  Committing URL updates...")
        session.commit()
        log(f"  URL updates committed")

        # Update parent article's ES document with new available_cefr_levels
        log(f"  Updating parent article in Elasticsearch...")
        try:
            from zeeguu.core.elastic.indexing import create_or_update_article

            create_or_update_article(original_article, session)
            log(f"  Elasticsearch update completed")
        except Exception as e:
            log(f"  WARNING: Failed to update parent article in ES: {e}")
            # Don't fail the whole operation just because ES update failed

        # Log grammar corrections if any were made
        if uncorrected_versions:
            log(f"  Logging grammar corrections...")
            try:
                from zeeguu.core.model.grammar_correction_log import (
                    GrammarCorrectionLog,
                    CorrectionFieldType,
                )
                from zeeguu.core.model.ai_generator import AIGenerator
                from .grammar_correction_service import ANTHROPIC_CORRECTION_MODEL

                field_to_enum = {
                    "title": CorrectionFieldType.TITLE,
                    "content": CorrectionFieldType.CONTENT,
                    "summary": CorrectionFieldType.SUMMARY,
                }

                # Get or create AIGenerator records
                simplification_ai_generator = AIGenerator.find_or_create(
                    session, model_name
                )
                correction_ai_generator = AIGenerator.find_or_create(
                    session, ANTHROPIC_CORRECTION_MODEL
                )

                for simplified_article in simplified_articles:
                    level = simplified_article.cefr_level
                    if level in uncorrected_versions and level in versions:
                        uncorrected = uncorrected_versions[level]
                        corrected = versions[level]

                        # Log each field if it changed
                        for field in ["title", "content", "summary"]:
                            if field in uncorrected and field in corrected:
                                GrammarCorrectionLog.log_correction(
                                    session=session,
                                    article_id=simplified_article.id,
                                    field_type=field_to_enum[field],
                                    original_text=uncorrected[field],
                                    corrected_text=corrected[field],
                                    language_id=original_article.language_id,
                                    correction_ai_generator_id=correction_ai_generator.id,
                                    simplification_ai_generator_id=simplification_ai_generator.id,
                                )

                session.commit()
                log(f"  Grammar corrections logged")
            except Exception as e:
                log(f"  WARNING: Failed to log grammar corrections: {e}")
                # Don't fail the whole operation just because logging failed

        # Collect classifications detected by LLM
        classifications = []
        if is_disturbing:
            log(f"  LLM detected disturbing content - will be tagged by caller")
            classifications.append(("DISTURBING", "LLM"))

        log(
            f"SUCCESS: Created {len(simplified_articles)} simplified versions for article {original_article.id}"
        )
        log(f"  Original level (AI-assessed): {original_level}")
        log(f"  Created levels: {[a.cefr_level for a in simplified_articles]}")
        log(f"  Article IDs: {[a.id for a in simplified_articles]}")
        return simplified_articles, classifications

    except Exception as e:
        error_msg = str(e)
        log(
            f"ERROR: Failed to auto-create simplified versions for article {original_article.id}"
        )
        log(f"  Error type: {type(e).__name__}")
        log(f"  Error message: {error_msg}")

        # Provide specific guidance for common errors
        if "incomplete due to paywall" in error_msg:
            log(
                f"  REASON: Article appears to be truncated by paywall - consider marking as broken"
            )
        elif "DEEPSEEK_API" in error_msg:
            log(f"  REASON: API key missing or invalid")
        elif "API error" in error_msg:
            log(f"  REASON: External API failure - may be temporary")
        else:
            log(f"  REASON: Unexpected error during simplification process")

        # Only rollback for specific database-related errors that might have corrupted the session
        # Don't rollback for API failures or missing configurations
        if (
            "IntegrityError" in str(type(e))
            or "DataError" in str(type(e))
            or "database" in error_msg.lower()
            or "constraint" in error_msg.lower()
        ):
            log(f"  DATABASE ERROR: Rolling back session due to database-related error")
            session.rollback()
        else:
            log(
                f"  NO ROLLBACK: Error is not database-related, preserving original article"
            )

        return [], []


def create_user_specific_simplified_version(session, article, target_level):
    """
    Create a single simplified version of an article for a specific CEFR level.
    Much faster than creating all levels.

    Args:
        session: Database session
        article: Original article to simplify
        target_level: CEFR level to create (e.g., "A2")

    Returns:
        Simplified Article object or None if failed
    """
    from zeeguu.logging import log

    log(f"Creating simplified version for article {article.id} at level {target_level}")

    try:
        # Get the original article's assessed level
        from zeeguu.core.language.fk_to_cefr import fk_to_cefr

        original_level = article.cefr_level or fk_to_cefr(article.get_fk_difficulty())

        # Don't simplify if target level is same or higher than original
        cefr_order = ["A1", "A2", "B1", "B2", "C1", "C2"]
        if target_level not in cefr_order or original_level not in cefr_order:
            log(
                f"Invalid CEFR levels: original={original_level}, target={target_level}"
            )
            return None

        target_index = cefr_order.index(target_level)
        original_index = cefr_order.index(original_level)

        if target_index >= original_index:
            log(
                f"Target level {target_level} is not simpler than original {original_level}"
            )
            return None

        # Create the simplified version using targeted prompt
        simplified_content = _create_targeted_simplified_version(
            article.content,
            article.title,
            article.language.code,
            original_level,
            target_level,
        )

        if not simplified_content:
            log(f"Failed to generate simplified content for {target_level}")
            return None

        # Create the new simplified article using the proper method with correct AI model info
        new_article = Article.create_simplified_version(
            session=session,
            parent_article=article,
            simplified_title=simplified_content["title"],
            simplified_content=simplified_content["content"],
            simplified_summary=simplified_content.get("summary", ""),
            cefr_level=target_level,
            ai_model=models.SIMPLIFICATION,  # provenance: primary model SimplificationService uses (Haiku; DeepSeek fallback)
            commit=True,
        )

        log(
            f"Successfully created simplified article {new_article.id} at {target_level} level"
        )
        return new_article

    except Exception as e:
        log(f"Error creating simplified version: {str(e)}")
        session.rollback()
        return None


def create_simplified_version_from_upload(session, upload, target_level):
    """
    Simplify an ArticleUpload directly at target_level. No parent Article
    is created; the resulting simplified Article stores source_upload_id
    as the back-reference. Returns the simplified Article or None.
    """
    from zeeguu.logging import log

    log(f"Creating simplified article from upload {upload.id} at level {target_level}")

    cefr_order = ["A1", "A2", "B1", "B2", "C1", "C2"]
    if target_level not in cefr_order:
        log(f"Invalid target CEFR level: {target_level}")
        return None

    if not upload.language:
        log(f"Upload {upload.id} has no detected language; cannot simplify")
        return None

    content = upload.text_content or upload.raw_html or ""
    title = upload.title or ""
    if not content.strip():
        log(f"Upload {upload.id} has no content to simplify")
        return None

    try:
        result = _create_targeted_simplified_version(
            content,
            title,
            upload.language.code,
            None,  # original_level unknown and unused by the service
            target_level,
        )
        if not result:
            log(f"Simplification LLM returned nothing for upload {upload.id}")
            return None

        return Article.create_simplified_version(
            session=session,
            source_upload=upload,
            simplified_title=result["title"],
            simplified_content=result["content"],
            simplified_summary=result.get("summary", ""),
            cefr_level=target_level,
            ai_model=models.SIMPLIFICATION,  # provenance: primary model SimplificationService uses (Haiku; DeepSeek fallback)
            commit=True,
        )
    except Exception as e:
        log(f"Error simplifying upload {upload.id}: {e}")
        session.rollback()
        return None


def _create_targeted_simplified_version(
    content, title, language_code, original_level, target_level
):
    """
    Create a simplified version targeting a specific CEFR level using the new SimplificationService.
    """
    from zeeguu.core.llm_services.simplification_service import (
        get_simplification_service,
    )

    service = get_simplification_service()
    return service.simplify_text(title, content, target_level, language_code)


def assess_article_cefr_level(title, content, language_code):
    """
    Assess the CEFR level of an article using LLM fallback chain (Anthropic → DeepSeek).

    Args:
        title: Article title
        content: Article content
        language_code: Language code (e.g., 'da', 'es')

    Returns:
        Tuple of (cefr_level, method) where:
        - cefr_level: CEFR level string (A1, A2, B1, B2, C1, C2) or None if failed
        - method: Assessment method used ("llm_assessed_anthropic" or "llm_assessed_deepseek")
    """
    from zeeguu.core.llm_services.simplification_service import (
        get_simplification_service,
    )

    service = get_simplification_service()
    cefr_level, topic, method = service.assess_cefr_and_topic_with_fallback(
        title, content, language_code
    )
    return (cefr_level, method)


def assess_article_cefr_level_deepseek_only(title, content, language_code):
    """
    Assess the CEFR level using DeepSeek only for consistency with batch crawling.
    Use this when creating clones/copies to ensure same model evaluates as during crawling.

    Args:
        title: Article title
        content: Article content
        language_code: Language code (e.g., 'da', 'es')

    Returns:
        CEFR level string (A1, A2, B1, B2, C1, C2) or None if failed
    """
    from zeeguu.core.llm_services.simplification_service import (
        get_simplification_service,
    )

    service = get_simplification_service()
    return service.assess_cefr_level_deepseek_only(title, content, language_code)

"""
Article simplification and content classification.

This module handles:
- Creating CEFR-level appropriate simplified versions of articles
- Classifying content (disturbing news, etc.)
- Both operations done in a single LLM call for efficiency
- Round-robin between DeepSeek and Anthropic for A/B comparison
"""

import os
import requests
import time
from requests.exceptions import Timeout, RequestException
from zeeguu.logging import log
from zeeguu.core.language.language_check import describe_mismatches
from zeeguu.core.language.generate_in_language import (
    LanguageMismatchError,
    generate_in_language,
)
from zeeguu.core.model.article import Article
from zeeguu.core.model.url import Url
from .haiku_client import HAIKU_MODEL, haiku_completion_or_raise
from .prompts.article_simplification import (
    get_adaptive_simplification_prompt,
    get_assessment_and_summary_prompt,
)
from zeeguu.core.llm_services import models


# Round-robin counter for alternating between providers
_simplification_provider_counter = 0


def _get_next_simplification_provider() -> str:
    """
    Round-robin between 'deepseek' and 'anthropic' for simplification.
    This allows A/B comparison of error rates between providers.
    """
    global _simplification_provider_counter
    _simplification_provider_counter += 1

    if _simplification_provider_counter % 2 == 0:
        return "deepseek"
    else:
        return "anthropic"


def _select_provider_and_key(simplification_provider: str = None):
    """
    Resolve the provider (round-robin unless one is given) and its API key,
    falling back to the other provider when the primary key is unset.
    Returns (provider, api_key). Shared by the assess-only and full-simplify paths.
    """
    if simplification_provider:
        provider = simplification_provider
    else:
        provider = _get_next_simplification_provider()
    log(f"Using {provider.upper()} provider for simplification")

    if provider == "deepseek":
        api_key = os.environ.get("DEEPSEEK_API_SIMPLIFICATIONS")
        fallback_api_key = os.environ.get("ANTHROPIC_TEXT_SIMPLIFICATION_KEY")
    else:
        api_key = os.environ.get("ANTHROPIC_TEXT_SIMPLIFICATION_KEY")
        fallback_api_key = os.environ.get("DEEPSEEK_API_SIMPLIFICATIONS")

    if not api_key:
        log(f"WARNING: {provider.upper()} API key not set, trying fallback")
        provider = "anthropic" if provider == "deepseek" else "deepseek"
        api_key = fallback_api_key
        if not api_key:
            raise Exception(
                "Neither DEEPSEEK_API_SIMPLIFICATIONS nor ANTHROPIC_TEXT_SIMPLIFICATION_KEY environment variable set"
            )
    return provider, api_key


def _call_simplification_llm(prompt, provider, api_key, max_tokens, timeout=180):
    """
    Send `prompt` to the chosen provider and return (result_text, model_name).
    Raises on a non-200 DeepSeek response or an Anthropic error.
    """
    api_start_time = time.time()
    if provider == "deepseek":
        model_name = models.DEEPSEEK_GENERAL
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.1,
            },
            timeout=timeout,
        )
        if response.status_code != 200:
            raise Exception(
                f"DEEPSEEK API error: {response.status_code} - {response.text}"
            )
        result = response.json()["choices"][0]["message"]["content"].strip()
    else:  # anthropic
        model_name = HAIKU_MODEL
        result = haiku_completion_or_raise(
            prompt, max_tokens=max_tokens, temperature=0.1, timeout=timeout
        ).strip()
    log(f"  {provider.upper()} responded in {time.time() - api_start_time:.2f}s ({len(result)} chars)")
    return result, model_name


def _raise_if_paywall_or_advertorial(result):
    """Both prompts answer with a bare token when the article is junk — reject it."""
    if result.lower().strip() == "unfinished":
        raise Exception("PAYWALL: Article appears to be incomplete due to paywall")
    if result.lower().strip() == "advertorial":
        raise Exception(
            "ADVERTORIAL: Article appears to be advertorial/promotional content"
        )


def _clean_text(text):
    return text.strip("[](){}\"'")


def _strip_markdown_from_summary(text):
    """Remove markdown bold/italic formatting from summary text."""
    import re

    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)
    return text


# Labels for the language check on the summaries. They double as the keys we use
# to drop exactly the summaries that came back in the wrong language.
ORIGINAL_SUMMARY_LABEL = "original summary"


def _level_summary_label(level: str) -> str:
    return f"{level} summary"


def _level_title_label(level: str) -> str:
    return f"{level} title"


def _summaries_to_check(assessment: dict) -> list:
    """
    The generated text out of an assessment, labelled — the only part of it that
    has a language. Each label is also the key we drop that piece by, so they have
    to match the ones _without_wrong_language_summaries looks for.

    Per-level titles are included, but a headline is short enough that the
    language check will often return "can't judge" (None) rather than a verdict;
    that is the check failing open on purpose, not a pass.
    """
    fields = [(ORIGINAL_SUMMARY_LABEL, assessment.get("original_summary", ""))]
    fields += [
        (_level_summary_label(level), text)
        for level, text in assessment.get("level_summaries", {}).items()
    ]
    fields += [
        (_level_title_label(level), text)
        for level, text in assessment.get("level_titles", {}).items()
    ]
    return fields


def _without_wrong_language_summaries(assessment: dict, mismatches: list) -> dict:
    """
    Policy for a summary that stayed English: drop it, keep the assessment.

    CEFR level, article type and the disturbing-content flag are language-
    independent and still correct, and the crawl path only overwrites
    ``article.summary`` when the summary is non-empty — so dropping one leaves
    the feed blurb in place rather than an English summary on a Danish article.
    """
    wrong = {m.label for m in mismatches}
    result = dict(assessment)
    if ORIGINAL_SUMMARY_LABEL in wrong:
        result["original_summary"] = ""
    result["level_summaries"] = {
        level: text
        for level, text in result.get("level_summaries", {}).items()
        if _level_summary_label(level) not in wrong
    }
    # A level's title and summary are dropped independently: an English title
    # next to a good Danish summary should cost us the title, not the summary.
    # The overlay falls back to the article's own title when a level has none.
    result["level_titles"] = {
        level: text
        for level, text in result.get("level_titles", {}).items()
        if _level_title_label(level) not in wrong
    }
    return result


def assess_and_summarize(
    title: str,
    content: str,
    target_language: str,
    simplification_provider: str = None,
) -> dict:
    """
    On-demand-pipeline crawl step: assess CEFR level, summarize, and classify an
    article in a single LLM call WITHOUT generating any simplified versions.

    This is the cheap replacement for ``simplify_article_adaptive_levels`` on the
    crawl path now that simplification is on-demand. It returns the same metadata
    fields the feed relies on and raises the same PAYWALL/ADVERTORIAL exceptions
    so the crawler's junk-rejection keeps working unchanged.

    Returns:
        {
            'original_cefr_level': str,
            'original_summary': str,
            'article_type': str | None,   # 'news' | 'general'
            'is_disturbing': bool,
            'provider': str,
            'model_name': str,
        }

    The summaries must be in the article's language; the LLM used to return
    English for half of them and nothing errored. They are re-requested once with
    the mismatch named, and dropped if they come back wrong again — the
    assessment itself is language-independent and always kept.

    Raises:
        Exception: "PAYWALL: ..." or "ADVERTORIAL: ..." when the LLM flags the
        article, or on API failure.
    """
    prompt_template = get_assessment_and_summary_prompt(target_language)
    prompt = prompt_template.format(title=title, content=content)

    provider, api_key = _select_provider_and_key(simplification_provider)
    log(f"Assessing+summarizing article '{title[:50]}...' in {target_language}")

    def generate(correction):
        # Assessment + one ~70-word summary PER level below the original (up to 5
        # for a C2 article) plus the original summary. 2000 gives headroom over the
        # single-summary sizing so the last-emitted levels aren't truncated — still
        # a fraction of the 6000 the full multi-level bodies needed.
        result, model_name = _call_simplification_llm(
            prompt + correction, provider, api_key, max_tokens=2000, timeout=120
        )
        _raise_if_paywall_or_advertorial(result)
        return _parse_assessment_and_summary(result, provider, model_name)

    try:
        return generate_in_language(
            generate,
            target_language,
            _summaries_to_check,
            f"summary of '{title[:50]}'",
        )
    except LanguageMismatchError as e:
        log(
            f"  Dropping wrong-language summaries for '{title[:50]}': "
            f"{describe_mismatches(e.mismatches)}"
        )
        return _without_wrong_language_summaries(e.result, e.mismatches)


def _parse_assessment_and_summary(result: str, provider: str, model_name: str) -> dict:
    # Parse the small set of labelled fields, plus any per-level [LEVEL]_SUMMARY
    # sections (e.g. "A1_SUMMARY:", "B1_SUMMARY:").
    sections = {}
    current_section = None
    current_content = []
    for line in result.split("\n"):
        line = line.strip()
        is_field = ":" in line and any(
            line.startswith(prefix)
            for prefix in [
                "DISTURBING_CONTENT",
                "ARTICLE_TYPE",
                "ORIGINAL_LEVEL",
                "ORIGINAL_SUMMARY",
                "SIMPLIFIED_LEVELS",
            ]
        )
        is_level_summary = "_SUMMARY:" in line and line.split("_SUMMARY:")[0] in [
            "A1",
            "A2",
            "B1",
            "B2",
            "C1",
            "C2",
        ]
        is_level_title = "_TITLE:" in line and line.split("_TITLE:")[0] in [
            "A1",
            "A2",
            "B1",
            "B2",
            "C1",
            "C2",
        ]
        if is_field or is_level_summary or is_level_title:
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = line.split(":")[0]
            current_content = [line.split(":", 1)[1].strip()]
        elif current_section:
            current_content.append(line)
    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    is_disturbing = _clean_text(sections.get("DISTURBING_CONTENT", "NO")).upper() == "YES"
    article_type_raw = _clean_text(sections.get("ARTICLE_TYPE", "")).upper()
    article_type = article_type_raw if article_type_raw in ["NEWS", "GENERAL"] else None
    original_level = _clean_text(sections.get("ORIGINAL_LEVEL", ""))
    original_summary = _strip_markdown_from_summary(
        _clean_text(sections.get("ORIGINAL_SUMMARY", ""))
    )

    # Per-level preview summaries (one per level simpler than the original).
    level_summaries = {}
    for level in ["A1", "A2", "B1", "B2", "C1", "C2"]:
        raw = sections.get(f"{level}_SUMMARY")
        if raw:
            text = _strip_markdown_from_summary(_clean_text(raw))
            if text:
                level_summaries[level] = text

    # Per-level headlines, same shape as the summaries. A title is one line by
    # construction, so collapse any stray wrapping the section parser picked up.
    level_titles = {}
    for level in ["A1", "A2", "B1", "B2", "C1", "C2"]:
        raw = sections.get(f"{level}_TITLE")
        if raw:
            text = _strip_markdown_from_summary(_clean_text(raw))
            text = " ".join(text.split())
            if text:
                level_titles[level] = text

    return {
        "original_cefr_level": original_level,
        "original_summary": original_summary,
        # Lowercase to match the DB enum('news','general') — the article_type
        # column uses a case-sensitive utf8mb4_bin collation, so an uppercase
        # value fails the write with "Data truncated for column 'article_type'"
        # and rolls back the whole crawl-time assessment. Mirrors the sibling
        # parser in simplify_and_classify below.
        "article_type": article_type.lower() if article_type else None,
        "is_disturbing": is_disturbing,
        "level_summaries": level_summaries,
        "level_titles": level_titles,
        "provider": provider,
        "model_name": model_name,
    }


def assess_summarize_and_classify(
    session, original_article: Article, simplification_provider: str = None
) -> tuple[list, list]:
    """
    Crawl-time entry point for the on-demand pipeline. Mirrors the return
    contract of ``simplify_and_classify`` — ``(simplified_articles, classifications)``
    — but NEVER creates simplified children: it only assesses the original's
    CEFR level, writes an abstractive summary, and detects article type and
    disturbing content. Simplification happens later, on demand, when a learner
    opens the article (POST /simplify_article/<id>).

    The empty ``simplified_articles`` list keeps the caller in
    ``article_downloader.py`` working with no branch changes, and PAYWALL/
    ADVERTORIAL exceptions propagate so junk rejection is unchanged.
    """
    if original_article.parent_article_id:
        log(
            f"SKIP: Article {original_article.id} is already a simplified version (parent: {original_article.parent_article_id})"
        )
        return [], []

    word_count = original_article.get_word_count()
    if word_count < 100:
        log(
            f"SKIP: Article {original_article.id} is too short to assess - {word_count} words (minimum: 100 words)"
        )
        return [], []

    log(f"STARTING: Assess+summarize (on-demand mode) for article {original_article.id}")

    result = assess_and_summarize(
        original_article.title,
        original_article.get_content(),
        original_article.language.code,
        simplification_provider=simplification_provider,
    )

    original_article.cefr_level = result["original_cefr_level"]
    if result["article_type"]:
        original_article.article_type = result["article_type"]
    # Prefer the LLM's abstractive summary over the feed's RSS blurb, which is
    # often just the headline reworded (and can be verbatim publisher text).
    if result["original_summary"]:
        original_article.summary = result["original_summary"]
    session.commit()

    # Persist the per-level preview summaries (tokenized so the tappable feed-card
    # preview renders without re-tokenizing on the request path).
    _store_level_summaries(
        session,
        original_article,
        result.get("level_summaries", {}),
        result.get("model_name"),
        result.get("level_titles", {}),
    )

    classifications = []
    if result["is_disturbing"]:
        classifications.append(("DISTURBING", "LLM"))
    return [], classifications


# Prompt-version tag so the first-class AIGenerator entity records which prompt
# produced these summaries (bump when the assess+summarize prompt changes).
ASSESS_SUMMARY_PROMPT_VERSION = "assess_summary_v1"


def _store_level_summaries(session, article, level_summaries, model_name, level_titles=None):
    """
    Create/refresh ArticleLevelSummary rows for an article, tokenizing each.

    A level's title is optional and stored alongside its summary: the LLM may not
    have produced one, or the language check may have dropped it while keeping the
    summary. The card falls back to the article's own title in that case, so a
    missing title is never a reason to skip the row.
    """
    if not level_summaries:
        return
    from zeeguu.core.model.article_level_summary import ArticleLevelSummary
    from zeeguu.core.model.ai_generator import AIGenerator
    from zeeguu.core.mwe import tokenize_for_reading

    level_titles = level_titles or {}

    ai_generator_id = None
    if model_name:
        ai_generator = AIGenerator.find_or_create(
            session, model_name, prompt_version=ASSESS_SUMMARY_PROMPT_VERSION
        )
        ai_generator_id = ai_generator.id

    def tokenized_or_none(text, what, level):
        try:
            return tokenize_for_reading(text, article.language, mode="stanza")
        except Exception as e:
            log(f"  Could not tokenize {level} {what} for article {article.id}: {e}")
            return None

    n_titles = 0
    for level, summary_text in level_summaries.items():
        title_text = level_titles.get(level)
        tokenized_title = None
        if title_text:
            tokenized_title = tokenized_or_none(title_text, "title", level)
            n_titles += 1
        ArticleLevelSummary.find_or_create(
            session,
            article,
            cefr_level=level,
            summary=summary_text,
            tokenized_summary=tokenized_or_none(summary_text, "summary", level),
            ai_generator_id=ai_generator_id,
            commit=False,
            title=title_text,
            tokenized_title=tokenized_title,
        )
    session.commit()
    log(
        f"  Stored {len(level_summaries)} per-level preview summaries "
        f"({n_titles} with titles) for article {article.id}"
    )


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


def _simplification_to_check(simplification: dict) -> list:
    """
    What a simplification run generated, one field per part.

    Not glued together per level: a level's Danish summary masks its English body
    when they are judged as one string — 0.97 plausible as Danish for a field whose
    content alone scores 0.00. Titles are short enough to answer "can't judge" on
    their own, which is the right answer for them.

    Nothing keys off these labels — a run that comes back wrong is lost whole (see
    simplify_article_adaptive_levels) — but naming the part makes the log say which
    one it was.
    """
    fields = [(ORIGINAL_SUMMARY_LABEL, simplification.get("original_summary", ""))]
    for level, version in simplification.get("versions", {}).items():
        for part in ("title", "summary", "content"):
            fields.append((f"{level} {part}", version.get(part, "")))
    return fields


def _parse_adaptive_response(result: str, provider: str, model_name: str) -> dict:
    """Turn one adaptive-simplification response into the levels it describes."""
    log(f"  Parsing response sections...")
    # Parse the response
    sections = {}
    lines = result.split("\n")
    current_section = None
    current_content = []

    for line in lines:
        line = line.strip()
        if ":" in line and any(
            line.startswith(prefix)
            for prefix in [
                "DISTURBING_CONTENT",
                "ARTICLE_TYPE",
                "ORIGINAL_LEVEL",
                "ORIGINAL_SUMMARY",
                "SIMPLIFIED_LEVELS",
            ]
        ):
            # Save previous section
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            # Start new section
            section_name = line.split(":")[0]
            current_section = section_name
            current_content = [line.split(":", 1)[1].strip()]
        elif "_TITLE:" in line or "_CONTENT:" in line or "_SUMMARY:" in line:
            # Save previous section
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            # Start new section
            section_name = line.split(":")[0]
            current_section = section_name
            current_content = [line.split(":", 1)[1].strip()]
        elif current_section:
            current_content.append(line)

    # Save last section
    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    log(f"  Found {len(sections)} sections in response")
    log(f"  Section keys: {list(sections.keys())}")

    # Extract basic info
    is_disturbing = (
        _clean_text(sections.get("DISTURBING_CONTENT", "NO")).upper() == "YES"
    )
    article_type_raw = _clean_text(sections.get("ARTICLE_TYPE", "")).upper()
    article_type = (
        article_type_raw if article_type_raw in ["NEWS", "GENERAL"] else None
    )
    original_level = _clean_text(sections.get("ORIGINAL_LEVEL", ""))
    original_summary = _strip_markdown_from_summary(
        _clean_text(sections.get("ORIGINAL_SUMMARY", ""))
    )
    simplified_levels_str = _clean_text(sections.get("SIMPLIFIED_LEVELS", ""))

    # Parse simplified levels
    if simplified_levels_str:
        simplified_levels = [
            level.strip() for level in simplified_levels_str.split(",")
        ]
    else:
        simplified_levels = []

    # Validate CEFR level
    valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    if original_level not in valid_levels:
        log(
            f"Warning: Invalid original CEFR level '{original_level}', defaulting to 'B2'"
        )
        original_level = "B2"

    log(
        f"  Extracted: original_level={original_level}, simplified_levels={simplified_levels}"
    )

    # Extract simplified versions
    log(f"  Extracting simplified versions for levels: {simplified_levels}")
    versions = {}
    for level in simplified_levels:
        log(f"    Processing level {level}...")
        title_key = f"{level}_TITLE"
        content_key = f"{level}_CONTENT"
        summary_key = f"{level}_SUMMARY"

        if all(key in sections for key in [title_key, content_key, summary_key]):
            versions[level] = {
                "title": _clean_text(sections[title_key]),
                "content": _clean_text(sections[content_key]),
                "summary": _strip_markdown_from_summary(
                    _clean_text(sections[summary_key])
                ),
            }
            log(f"    Successfully extracted {level} version")
        else:
            missing_keys = [
                key
                for key in [title_key, content_key, summary_key]
                if key not in sections
            ]
            log(f"    Missing keys for {level}: {missing_keys}")

    # Validate we got the expected content
    if not original_summary:
        raise Exception("Missing original summary in response")

    # Filter out incomplete levels but keep the ones that are complete
    valid_levels = []
    invalid_levels = []
    for level in simplified_levels:
        if level in versions and all(versions[level].values()):
            valid_levels.append(level)
        else:
            invalid_levels.append(level)
            log(
                f"  Warning: Missing or incomplete content for {level} level, skipping"
            )

    # Update simplified_levels to only include valid ones
    simplified_levels = valid_levels

    # Only fail if we got NO valid levels at all
    if not simplified_levels:
        raise Exception(
            f"No complete simplified versions were created. Incomplete levels: {invalid_levels}"
        )

    if invalid_levels:
        log(
            f"Partially successful: simplified article to {len(simplified_levels)} levels: {simplified_levels} (skipped incomplete: {invalid_levels})"
        )
    else:
        log(
            f"Successfully simplified article to {len(simplified_levels)} levels: {simplified_levels} (original was {original_level}, disturbing: {is_disturbing})"
        )

    return {
        "is_disturbing": is_disturbing,
        "article_type": article_type.lower() if article_type else None,
        "original_cefr_level": original_level,
        "original_summary": original_summary,
        "simplified_levels": simplified_levels,
        "versions": versions,
        "provider": provider,
        "model_name": model_name,
    }


def simplify_article_adaptive_levels(
    title: str,
    content: str,
    target_language: str,
    model: str = models.DEEPSEEK_GENERAL,
    simplification_provider: str = None,
    correct_grammar: bool = False,
) -> dict:
    """
    Simplify article to all levels simpler than the original using a single API call.
    Uses DeepSeek by default (Anthropic used in parallel mode for A/B comparison).

    Args:
        title: Original article title
        content: Original article content
        target_language: Language code (e.g., 'da', 'es')
        model: Model to use (deprecated, provider chosen automatically)
        simplification_provider: Provider to use ('deepseek' or 'anthropic'), overrides default if set
        correct_grammar: Whether to run a separate Haiku grammar/spelling correction pass after simplification. Default is False — the DeepSeek + Haiku correction experiment ran 2025-12-09 → 2026-04-05 and concluded that the corrections were overwhelmingly cosmetic (~96% of title fixes and ~72% of content fixes were ≤2 char diffs). The correction pass and grammar_correction_log writes are kept in place but disabled by default; data from the experiment is preserved in the table.

    Returns:
        Dict containing all simplified versions and original metadata:
        {
            'original_cefr_level': str,
            'original_summary': str,
            'simplified_levels': list[str],  # e.g., ['A1', 'A2', 'B1']
            'versions': {
                'A1': {'title': str, 'content': str, 'summary': str},
                'A2': {'title': str, 'content': str, 'summary': str},
                ...
            },
            'provider': str,  # 'deepseek' or 'anthropic'
            'model_name': str  # e.g., 'deepseek-chat' or 'claude-haiku-4-5-20251001'
        }

    The whole set must come back in the article's language. If it doesn't, it is
    re-requested once with the mistake named, and then the run fails — no level
    is salvaged from a response that came back in the wrong language twice.

    Raises:
        Exception: If API call fails, returns unexpected response, or the output
        is still in the wrong language after the retry
    """

    # Get the adaptive prompt
    prompt_template = get_adaptive_simplification_prompt(target_language)
    prompt = prompt_template.format(title=title, content=content)

    provider, api_key = _select_provider_and_key(simplification_provider)

    try:
        log(f"Adaptively simplifying article '{title[:50]}...' in {target_language}")
        log(f"  Article length: {len(content)} characters")
        log(f"  Prompt length: {len(prompt)} characters")

        def generate(correction):
            result, model_name = _call_simplification_llm(
                prompt + correction, provider, api_key, max_tokens=6000, timeout=180
            )
            _raise_if_paywall_or_advertorial(result)
            return _parse_adaptive_response(result, provider, model_name)

        simplification = generate_in_language(
            generate,
            target_language,
            _simplification_to_check,
            f"simplification of '{title[:50]}'",
        )

        versions = simplification["versions"]
        simplified_levels = simplification["simplified_levels"]

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
                import copy

                uncorrected_versions = copy.deepcopy(versions)

                for level in simplified_levels:
                    if level in versions:
                        log(f"    Correcting {level} version...")
                        corrected = grammar_service.correct_simplified_version(
                            versions[level], target_language, provider="anthropic"
                        )
                        versions[level] = corrected
                        log(f"    {level} version corrected")

                log(f"  Grammar correction completed for all levels")
            except Exception as e:
                # Log but don't fail - uncorrected simplification is better than no simplification
                log(
                    f"  WARNING: Grammar correction failed, using uncorrected versions: {e}"
                )
                uncorrected_versions = None  # Don't log if correction failed

        # For logging corrections
        simplification["uncorrected_versions"] = uncorrected_versions
        return simplification

    except Timeout as e:
        log(f"  ERROR: DeepSeek API call timed out after 3 minutes")
        raise Exception(
            f"Failed to adaptively simplify article: API timeout after 180 seconds"
        )
    except RequestException as e:
        log(f"  ERROR: Network error during API call: {str(e)}")
        raise Exception(
            f"Failed to adaptively simplify article: Network error - {str(e)}"
        )
    except Exception as e:
        log(f"  ERROR: Unexpected error: {str(e)}")
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
    for existing in original_article.available_simplified_versions:
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
        # Prefer the LLM's abstractive summary over the feed's RSS blurb, which is
        # often just the headline reworded (and can be verbatim publisher text).
        # Keep whatever's already there only as a fallback when the LLM produced
        # no summary.
        if original_summary:
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
            ai_model=model_name,
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

    Uses a single LLM call to:
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
        # Use the adaptive approach - single API call for assessment and all simplifications
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
        # Prefer the LLM's abstractive summary over the feed's RSS blurb, which is
        # often just the headline reworded (and can be verbatim publisher text).
        # Keep whatever's already there only as a fallback when the LLM produced
        # no summary.
        if original_summary:
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
                    ai_model=model_name,
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


def create_recipient_derivative_from_article(
    session, article, target_language_code, target_level
):
    """A recipient's personalized copy generated from a crawled ARTICLE (no upload).

    The multiplexer for *feed* shares. Both variants create a child of the
    original (``parent_article_id``) so the reader's ``Original:`` link works,
    ``is_translated``/``is_simplified`` derive, and it coalesces per
    (original, language, level):

      - **same language**: simplify to the recipient's level.
      - **cross language**: translate + adapt into the recipient's language.
        (The recommender overlay is guarded to *same-language* children, so a
        translated child is never shown as the original's "simplified version".)

    Returns the Article, or ``None`` (recipient opens the original and adapts)
    when no simplification is needed (level ≥ the article's) or generation fails.
    """
    from zeeguu.core.model.article import Article

    if not article.language:
        return None
    source_language_code = article.language.code

    # Same language → simplify to the recipient's level. Filter the cache by
    # language too: cross-language translated children now also hang off this
    # parent, so parent+level alone could match one of those.
    if target_language_code == source_language_code:
        existing = (
            Article.query.filter_by(
                parent_article_id=article.id, cefr_level=target_level
            )
            .filter(Article.language_id == article.language_id)
            .first()
        )
        if existing:
            return existing
        return create_user_specific_simplified_version(session, article, target_level)

    # Cross language → translate + adapt into the recipient's language, as a
    # child of the original. Cached under the #translated-from URL key.
    from zeeguu.core.model import Language
    from zeeguu.core.model.url import Url
    from zeeguu.core.model.source import Source
    from zeeguu.core.model.source_type import SourceType
    from zeeguu.core.llm_services.simplification_service import SimplificationService
    from datetime import datetime
    import markdown2

    target_lang = Language.find(target_language_code)
    if target_lang is None:
        return None
    translated_url_key = (
        f"{article.url.as_string()}"
        f"#translated-from-{source_language_code}-to-{target_language_code}-{target_level}"
    )
    existing = Article.find(translated_url_key)
    # Skip a copy marked broken — the audit tool marks wrong-language ones, and
    # this URL-key cache is the only thing that would otherwise keep serving it.
    if existing and not existing.broken:
        return existing

    content = article.content or ""
    title = article.title or ""
    if not content.strip():
        return None
    result = SimplificationService().translate_and_adapt(
        title=title,
        content=content,
        source_language=source_language_code,
        target_language=target_language_code,
        target_level=target_level,
    )
    if not result:
        return None

    translated_url = Url.find_or_create(session, translated_url_key)
    source_type = SourceType.find_by_type(SourceType.ARTICLE)
    source_obj = Source.find_or_create(
        session, result["content"], source_type, target_lang, 0
    )
    clean_summary = result.get("summary") or (result["content"][:200] + "...")
    html = result["content"]
    if html and not html.strip().startswith("<"):
        html = markdown2.markdown(
            html, extras=["break-on-newline", "fenced-code-blocks", "tables"]
        )

    translated = Article(
        translated_url,
        result["title"],
        "",
        source_obj,
        clean_summary,
        article.published_time or datetime.now(),
        None,
        target_lang,
        html,
        None,
    )
    translated.cefr_level = target_level
    # Child of the original: gives the reader's Original: link (parent_url),
    # makes is_translated derive (language != parent's), and coalesces. Safe
    # for the recommender because its overlay is filtered to same-language.
    translated.parent_article_id = article.id
    if article.img_url:
        translated.img_url = article.img_url

    session.add(translated)
    session.commit()
    translated.create_article_fragments(session)
    session.commit()
    return translated


def create_recipient_derivative(session, upload, target_language_code, target_level):
    """A recipient's personalized full-body copy, generated from a SHARER's upload.

    The multiplexer's "out" side: the sharer captured the full body (`upload`),
    and each recipient reads it in *their* language at *their* level.

      - **same language** (target == upload.language): simplify to ``target_level``.
      - **cross language**: translate + adapt to ``target_language_code``.

    Cached per (upload, language, level) — the same-language variant via
    (source_upload_id, cefr_level, language), the cross-language variant via the
    ``#translated-from-…`` URL key — so a second recipient at the same
    language+level reuses the first one's article. Returns the Article, or
    ``None`` if generation failed (too long / LLM error).
    """
    from zeeguu.core.model.article import Article
    from zeeguu.core.model import Language
    from zeeguu.core.model.url import Url
    from zeeguu.core.model.source import Source
    from zeeguu.core.model.source_type import SourceType
    from zeeguu.core.llm_services.simplification_service import SimplificationService
    from datetime import datetime
    from zeeguu.logging import log

    if not upload.language:
        log(f"Upload {upload.id} has no language; cannot build recipient derivative")
        return None
    source_language_code = upload.language.code

    # Same language → simplify to level (reuse the upload-simplify path + cache).
    if target_language_code == source_language_code:
        existing = (
            Article.query.filter_by(
                source_upload_id=upload.id,
                cefr_level=target_level,
                language_id=upload.language_id,
            )
            .filter(Article.parent_article_id.is_(None))
            .first()
        )
        if existing:
            return existing
        return create_simplified_version_from_upload(session, upload, target_level)

    # Cross language → translate + adapt, cached under the #translated-from key
    # (mirrors POST /article_upload/<id>/translate_and_adapt).
    translated_url_key = (
        f"{upload.url.as_string()}"
        f"#translated-from-{source_language_code}-to-{target_language_code}-{target_level}"
    )
    existing = Article.find(translated_url_key)
    # Skip a copy marked broken — the audit tool marks wrong-language ones, and
    # this URL-key cache is the only thing that would otherwise keep serving it.
    if existing and not existing.broken:
        return existing

    content = upload.text_content or upload.raw_html or ""
    title = upload.title or ""
    if not content.strip():
        return None

    try:
        result = SimplificationService().translate_and_adapt(
            title=title,
            content=content,
            source_language=source_language_code,
            target_language=target_language_code,
            target_level=target_level,
        )
    except Exception as e:
        log(f"translate_and_adapt failed for upload {upload.id}: {e}")
        return None
    if not result:
        log(f"translate_and_adapt returned nothing for upload {upload.id}")
        return None

    translated_url = Url.find_or_create(session, translated_url_key)
    target_lang_obj = Language.find(target_language_code)
    source_type = SourceType.find_by_type(SourceType.ARTICLE)
    source_obj = Source.find_or_create(
        session, result["content"], source_type, target_lang_obj, 0
    )
    clean_summary = result.get("summary") or (result["content"][:200] + "...")

    translated = Article(
        translated_url,
        result["title"],
        None,
        source_obj,
        clean_summary,
        datetime.now(),
        None,
        target_lang_obj,
        result["content"],
        None,
    )
    translated.cefr_level = target_level
    translated.source_upload_id = upload.id
    if upload.image_url:
        translated.img_url = Url.find_or_create(session, upload.image_url)

    session.add(translated)
    session.commit()
    translated.create_article_fragments(session)
    session.commit()
    return translated


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

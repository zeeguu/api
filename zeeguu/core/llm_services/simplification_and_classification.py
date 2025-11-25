"""
Article simplification and content classification using DeepSeek API.

This module handles:
- Creating CEFR-level appropriate simplified versions of articles
- Classifying content (disturbing news, etc.)
- Both operations done in a single LLM call for efficiency
"""

import os
import requests
import time
from requests.exceptions import Timeout, RequestException
from zeeguu.logging import log
from zeeguu.core.model.article import Article
from zeeguu.core.model.url import Url
from .prompts.article_simplification import get_adaptive_simplification_prompt


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




def simplify_article_adaptive_levels(
    title: str, content: str, target_language: str, model: str = "deepseek-chat", simplification_provider: str = None
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
            'model_name': str  # e.g., 'deepseek-chat' or 'claude-3-haiku-20240307'
        }

    Raises:
        Exception: If API call fails or returns unexpected response
    """

    # Get the adaptive prompt
    prompt_template = get_adaptive_simplification_prompt(target_language)
    prompt = prompt_template.format(title=title, content=content)

    # Use specified provider if set (for parallel processing), otherwise default to DeepSeek
    provider = simplification_provider if simplification_provider else 'deepseek'
    log(f"Using {provider.upper()} provider for simplification")

    # Try the chosen provider first, fallback to the other if it fails
    if provider == 'deepseek':
        api_key = os.environ.get("DEEPSEEK_API_SIMPLIFICATIONS")
        fallback_api_key = os.environ.get("ANTHROPIC_TEXT_SIMPLIFICATION_KEY")
    else:
        api_key = os.environ.get("ANTHROPIC_TEXT_SIMPLIFICATION_KEY")
        fallback_api_key = os.environ.get("DEEPSEEK_API_SIMPLIFICATIONS")

    if not api_key:
        log(f"WARNING: {provider.upper()} API key not set, trying fallback")
        provider = 'anthropic' if provider == 'deepseek' else 'deepseek'
        api_key = fallback_api_key
        if not api_key:
            raise Exception("Neither DEEPSEEK_API_SIMPLIFICATIONS nor ANTHROPIC_TEXT_SIMPLIFICATION_KEY environment variable set")

    try:
        log(f"Adaptively simplifying article '{title[:50]}...' in {target_language}")
        log(f"  Article length: {len(content)} characters")
        log(f"  Prompt length: {len(prompt)} characters")

        # Make API call based on provider
        api_start_time = time.time()

        if provider == 'deepseek':
            model_name = "deepseek-chat"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            data = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 6000,
                "temperature": 0.1,
            }
            log(f"  Sending request to DeepSeek API...")
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=180
            )
        else:  # anthropic
            model_name = "claude-3-haiku-20240307"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            data = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4000,
                "temperature": 0.1,
            }
            log(f"  Sending request to Anthropic API...")
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data,
                timeout=180
            )

        api_duration = time.time() - api_start_time
        log(f"  {provider.upper()} API responded with status: {response.status_code} (took {api_duration:.2f} seconds)")

        if response.status_code != 200:
            raise Exception(
                f"{provider.upper()} API error: {response.status_code} - {response.text}"
            )

        log(f"  Parsing {provider.upper()} API response...")
        response_json = response.json()

        # Extract result based on provider
        if provider == 'deepseek':
            result = response_json["choices"][0]["message"]["content"].strip()
        else:  # anthropic
            result = response_json["content"][0]["text"].strip()
        log(f"  Response length: {len(result)} characters")

        # Check if article is unfinished due to paywall
        if result.lower().strip() == "unfinished":
            raise Exception("PAYWALL: Article appears to be incomplete due to paywall")

        # Check if article is advertorial
        if result.lower().strip() == "advertorial":
            raise Exception("ADVERTORIAL: Article appears to be advertorial/promotional content")

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
        def clean_text(text):
            return text.strip("[](){}\"'")

        is_disturbing = clean_text(sections.get("DISTURBING_CONTENT", "NO")).upper() == "YES"
        original_level = clean_text(sections.get("ORIGINAL_LEVEL", ""))
        original_summary = clean_text(sections.get("ORIGINAL_SUMMARY", ""))
        simplified_levels_str = clean_text(sections.get("SIMPLIFIED_LEVELS", ""))

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

        log(f"  Extracted: original_level={original_level}, simplified_levels={simplified_levels}")

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
                    "title": clean_text(sections[title_key]),
                    "content": clean_text(sections[content_key]),
                    "summary": clean_text(sections[summary_key]),
                }
                log(f"    Successfully extracted {level} version")
            else:
                missing_keys = [key for key in [title_key, content_key, summary_key] if key not in sections]
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
                log(f"  Warning: Missing or incomplete content for {level} level, skipping")

        # Update simplified_levels to only include valid ones
        simplified_levels = valid_levels

        # Only fail if we got NO valid levels at all
        if not simplified_levels:
            raise Exception(f"No complete simplified versions were created. Incomplete levels: {invalid_levels}")

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
            "original_cefr_level": original_level,
            "original_summary": original_summary,
            "simplified_levels": simplified_levels,
            "versions": versions,
            "provider": provider,
            "model_name": model_name,
        }

    except Timeout as e:
        log(f"  ERROR: DeepSeek API call timed out after 3 minutes")
        raise Exception(f"Failed to adaptively simplify article: API timeout after 180 seconds")
    except RequestException as e:
        log(f"  ERROR: Network error during API call: {str(e)}")
        raise Exception(f"Failed to adaptively simplify article: Network error - {str(e)}")
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
        log(f"  Request details: title_len={len(title)}, content_len={len(content)}, language={language_code}")
        result = simplify_article_adaptive_levels(title, content, language_code, simplification_provider=simplification_provider)
        log(f"  LLM call completed successfully")

        # Extract the results
        is_disturbing = result.get("is_disturbing", False)
        original_level = result["original_cefr_level"]
        original_summary = result["original_summary"]
        simplified_levels = result["simplified_levels"]
        versions = result["versions"]
        provider = result["provider"]
        model_name = result["model_name"]

        log(f"  LLM Assessment complete:")
        log(f"    Provider used: {provider.upper()} ({model_name})")
        log(f"    Original level: {original_level}")
        log(f"    Simplified levels to create: {simplified_levels}")
        log(f"    Versions returned by LLM: {list(versions.keys())}")
        log(f"    Disturbing content detected: {is_disturbing}")

        if not simplified_levels:
            log(
                f"SKIP: Article {original_article.id} is already at {original_level} level - no simpler versions needed (AI assessment)"
            )
            # Return classifications even if no simplification needed
            classifications = []
            if is_disturbing:
                classifications.append(("DISTURBING", "LLM"))
            return [], classifications

        # Update the original article with assessed metadata
        log(f"  Updating original article metadata...")
        original_article.cefr_level = original_level
        if not original_article.summary:
            original_article.summary = original_summary

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
        log(f"  Committing {len(simplified_articles)} simplified articles to database...")
        session.commit()
        log(f"  Database commit completed")

        # Update URLs for all simplified articles now that they have IDs
        log(f"  Updating URLs for simplified articles...")
        for simplified_article in simplified_articles:
            log(f"    Updating URL for article {simplified_article.id} ({simplified_article.cefr_level})")
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
            log(f"Invalid CEFR levels: original={original_level}, target={target_level}")
            return None
            
        target_index = cefr_order.index(target_level)
        original_index = cefr_order.index(original_level)
        
        if target_index >= original_index:
            log(f"Target level {target_level} is not simpler than original {original_level}")
            return None

        # Create the simplified version using targeted prompt
        simplified_content = _create_targeted_simplified_version(
            article.content, 
            article.title,
            article.language.code,
            original_level,
            target_level
        )
        
        if not simplified_content:
            log(f"Failed to generate simplified content for {target_level}")
            return None

        # Create the new simplified article using the proper method with correct AI model info
        new_article = Article.create_simplified_version(
            session=session,
            parent_article=article,
            simplified_title=simplified_content['title'],
            simplified_content=simplified_content['content'],
            simplified_summary=simplified_content.get('summary', ''),
            cefr_level=target_level,
            ai_model="claude-3-5-sonnet",  # Match what SimplificationService actually uses
            commit=True
        )

        log(f"Successfully created simplified article {new_article.id} at {target_level} level")
        return new_article

    except Exception as e:
        log(f"Error creating simplified version: {str(e)}")
        session.rollback()
        return None


def _create_targeted_simplified_version(content, title, language_code, original_level, target_level):
    """
    Create a simplified version targeting a specific CEFR level using the new SimplificationService.
    """
    from zeeguu.core.llm_services.simplification_service import get_simplification_service
    
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
    from zeeguu.core.llm_services.simplification_service import get_simplification_service

    service = get_simplification_service()
    cefr_level, topic, method = service.assess_cefr_and_topic_with_fallback(title, content, language_code)
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
    from zeeguu.core.llm_services.simplification_service import get_simplification_service

    service = get_simplification_service()
    return service.assess_cefr_level_deepseek_only(title, content, language_code)

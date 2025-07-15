"""
Content simplifier for creating CEFR-level appropriate versions of articles using DeepSeek API.
"""

import os
import requests
from zeeguu.logging import log
from zeeguu.core.model.article import Article
from zeeguu.core.model.url import Url


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


def get_adaptive_simplification_prompt(language: str) -> str:
    """
    Get the prompt template for creating all simplified versions based on the original article's level.
    """
    language_names = {
        "da": "Danish",
        "es": "Spanish",
        "en": "English",
        "de": "German",
        "fr": "French",
        "nl": "Dutch",
        "it": "Italian",
        "pt": "Portuguese",
    }

    language_name = language_names.get(language, language)

    return f"""You are an expert {language_name} language teacher. Your task is to assess an article's CEFR level and create simplified versions for ALL levels that are simpler than the original.

CEFR Level Guidelines:
- A1: Very basic vocabulary (1000 most common words), simple present tense, basic sentence structures
- A2: Expanded vocabulary (2000 words), past/future tenses, simple connectors
- B1: Intermediate vocabulary (3000 words), complex sentences, opinion expressions
- B2: Advanced vocabulary, subjunctive mood, nuanced expressions
- C1: Sophisticated vocabulary, complex grammar, idiomatic expressions
- C2: Near-native level, literary devices, specialized terminology

IMPORTANT: If the article appears to be incomplete due to a paywall, simply respond with: "unfinished". This includes:
- Articles with fewer than 3 paragraphs (very likely incomplete)
- Articles that end abruptly without a proper conclusion
- Articles that appear to be only the first paragraph(s) of a longer piece
- Articles with "subscribe to read more" or similar paywall messages
- Articles that seem to cut off mid-story or mid-explanation
- Articles that lack the depth/detail expected from the headline

INSTRUCTIONS:
1. First assess the original article's CEFR level
2. Create simplified versions for ALL levels simpler than the original
3. If original is A1, create no simplified versions
4. If original is A2, create only A1
5. If original is B1, create A1 and A2
6. If original is B2, create A1, A2, and B1
7. If original is C1, create A1, A2, B1, and B2
8. If original is C2, create A1, A2, B1, B2, and C1

SIMPLIFICATION RULES:
- PRESERVE ALL MAIN IDEAS: Every important concept from the original must appear in simplified versions
- PRESERVE PARAGRAPH STRUCTURE: Transform each paragraph of the original into a paragraph in the simplified version
- MAINTAIN CONTENT DEPTH: Simplified versions should have 70-90% of the original length with simpler language
- PRESERVE ALL DETAILS: Include all examples, numbers, names, and specific information from the original
- DO NOT SUMMARIZE: This is simplification (easier language), not summarization (shorter content)
- PARAGRAPH-BY-PARAGRAPH: Work through each original paragraph and simplify its language while keeping all its content
- For A1: Use basic vocabulary (1000 words) and simple sentences, but express ALL the original ideas
  Example: "Scientists conducted research" → "Scientists did research" (NOT "There was research")
- For A2: Use expanded vocabulary (2000 words) with simple connectors, but maintain ALL details  
  Example: Include all facts, numbers, examples, and explanations from the original
- For B1+: Use appropriate complexity while preserving ALL original content and structure
- IMPORTANT: If original has 5 paragraphs, simplified version should have 5 paragraphs too

You must respond in the exact format shown below. Do NOT include any explanations, comments, or meta-text. The simplifications should all be done in {language_name}.

ORIGINAL_LEVEL: [assess the CEFR level of the original article: A1, A2, B1, B2, C1, or C2]

ORIGINAL_SUMMARY: [write a 3-sentence summary of the original article in {language_name} at its original CEFR level]

SIMPLIFIED_LEVELS: [list the levels you will create, e.g., "A1,A2" or "A1,A2,B1" - leave empty if original is A1]

[For each level in SIMPLIFIED_LEVELS, include these sections:]

[LEVEL]_TITLE: [write simplified title in {language_name}]

[LEVEL]_CONTENT: [write simplified content in {language_name}]

[LEVEL]_SUMMARY: [write 3-sentence summary in {language_name}]

Original article to simplify:

TITLE: {{title}}

CONTENT: {{content}}"""


def simplify_article_adaptive_levels(
    title: str, content: str, target_language: str, model: str = "deepseek-chat"
) -> dict:
    """
    Simplify article to all levels simpler than the original using a single API call.
    The LLM assesses the original level and creates all appropriate simplified versions.

    Args:
        title: Original article title
        content: Original article content
        target_language: Language code (e.g., 'da', 'es')
        model: DeepSeek model to use

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
            }
        }

    Raises:
        Exception: If API call fails or returns unexpected response
    """

    # Get the adaptive prompt
    prompt_template = get_adaptive_simplification_prompt(target_language)
    prompt = prompt_template.format(title=title, content=content)

    # Initialize DeepSeek client
    api_key = os.environ.get("DEEPSEEK_API_SIMPLIFICATIONS")
    if not api_key:
        raise Exception("DEEPSEEK_API_SIMPLIFICATIONS environment variable not set")

    try:
        log(f"Adaptively simplifying article '{title[:50]}...' in {target_language}")

        # Make DeepSeek API call
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 6000,  # Increased for multiple levels
            "temperature": 0.1,
        }

        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions", headers=headers, json=data
        )

        if response.status_code != 200:
            raise Exception(
                f"DeepSeek API error: {response.status_code} - {response.text}"
            )

        response_json = response.json()
        result = response_json["choices"][0]["message"]["content"].strip()

        # Check if article is unfinished due to paywall
        if result.lower().strip() == "unfinished":
            raise Exception("Article appears to be incomplete due to paywall")

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

        # Extract basic info
        def clean_text(text):
            return text.strip("[](){}\"'")

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

        # Extract simplified versions
        versions = {}
        for level in simplified_levels:
            title_key = f"{level}_TITLE"
            content_key = f"{level}_CONTENT"
            summary_key = f"{level}_SUMMARY"

            if all(key in sections for key in [title_key, content_key, summary_key]):
                versions[level] = {
                    "title": clean_text(sections[title_key]),
                    "content": clean_text(sections[content_key]),
                    "summary": clean_text(sections[summary_key]),
                }

        # Validate we got the expected content
        if not original_summary:
            raise Exception("Missing original summary in response")

        for level in simplified_levels:
            if level not in versions or not all(versions[level].values()):
                raise Exception(f"Missing or incomplete content for {level} level")

        log(
            f"Successfully simplified article to {len(simplified_levels)} levels: {simplified_levels} (original was {original_level})"
        )

        return {
            "original_cefr_level": original_level,
            "original_summary": original_summary,
            "simplified_levels": simplified_levels,
            "versions": versions,
        }

    except Exception as e:
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
        model_name = "deepseek-chat"

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


def auto_create_simplified_versions(
    session, original_article: Article
) -> list[Article]:
    """
    Automatically create simplified versions for new articles based on LLM-assessed CEFR level.
    Uses a single API call to assess the original level and create all appropriate simplified versions.
    This function is designed to be called by the crawler/article creation process.

    Args:
        session: Database session
        original_article: The original article to simplify

    Returns:
        List of created simplified articles
    """

    # Only create simplified versions for articles that don't already have them
    # and are not themselves simplified versions
    if original_article.parent_article_id:
        log(
            f"SKIP: Article {original_article.id} is already a simplified version (parent: {original_article.parent_article_id})"
        )
        return []

    if original_article.simplified_versions:
        existing_levels = [v.cefr_level for v in original_article.simplified_versions]
        log(
            f"SKIP: Article {original_article.id} already has {len(original_article.simplified_versions)} simplified versions: {existing_levels}"
        )
        return []

    # Only simplify articles with substantial content
    word_count = original_article.get_word_count()
    if word_count < 100:
        log(
            f"SKIP: Article {original_article.id} is too short for simplification - {word_count} words (minimum: 100 words)"
        )
        return []

    log(
        f"STARTING: Auto-creating simplified versions for article {original_article.id}"
    )
    log(f"  Title: {original_article.title[:100]}...")
    log(f"  Language: {original_article.language.code}")
    log(f"  Word count: {word_count}")

    try:
        # Use the new adaptive approach - single API call for assessment and all simplifications
        title = original_article.title
        content = original_article.get_content()
        language_code = original_article.language.code

        log(f"  Calling LLM for assessment and simplification...")
        result = simplify_article_adaptive_levels(title, content, language_code)

        # Extract the results
        original_level = result["original_cefr_level"]
        original_summary = result["original_summary"]
        simplified_levels = result["simplified_levels"]
        versions = result["versions"]

        log(f"  LLM Assessment complete:")
        log(f"    Original level: {original_level}")
        log(f"    Simplified levels to create: {simplified_levels}")
        log(f"    Versions returned by LLM: {list(versions.keys())}")

        if not simplified_levels:
            log(
                f"SKIP: Article {original_article.id} is already at {original_level} level - no simpler versions needed (AI assessment)"
            )
            return []

        # Update the original article with assessed metadata
        original_article.cefr_level = original_level
        if not original_article.summary:
            original_article.summary = original_summary

        # Create all simplified articles
        simplified_articles = []
        model_name = "deepseek-chat"

        for level in simplified_levels:
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

        # Commit all changes
        session.commit()

        # Update URLs for all simplified articles now that they have IDs
        for simplified_article in simplified_articles:
            final_url_string = f"https://zeeguu.org/read/article?id={simplified_article.id}"
            final_url = Url.find_or_create(session, final_url_string)
            simplified_article.url = final_url
            session.add(simplified_article)
        
        # Commit URL updates
        session.commit()

        log(
            f"SUCCESS: Created {len(simplified_articles)} simplified versions for article {original_article.id}"
        )
        log(f"  Original level (AI-assessed): {original_level}")
        log(f"  Created levels: {[a.cefr_level for a in simplified_articles]}")
        log(f"  Article IDs: {[a.id for a in simplified_articles]}")
        return simplified_articles

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

        session.rollback()
        return []

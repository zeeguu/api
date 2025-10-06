"""
Advertorial detection for filtering promotional content.

This module provides URL pattern matching and keyword detection
to identify advertorial/promotional content before expensive LLM processing.
"""

# URL patterns that indicate advertorial content
ADVERTORIAL_URL_PATTERNS = [
    "/bons-plans/",
    "/bon-plan/",
    "/shopping/",
    "/offre/",
    "/offres/",
    "/promo/",
    "/promotions/",
    "/deals/",
    "/bargain/",
    "/discount/",
    "/sale/",
    # Add more patterns as discovered
]

# Keywords that frequently appear in advertorial titles/URLs
# These should be checked in combination with context
ADVERTORIAL_KEYWORDS = [
    "rakuten",
    "amazon",
    "ne laissez pas passer",
    "meilleure offre",
    "bon plan",
    "à ne pas manquer",
    "en promotion",
    "en solde",
    "réduction",
    "-30%",
    "-40%",
    "-50%",
    "% de réduction",
    "code promo",
    "livraison gratuite",
    # Add more keywords as discovered
]


def is_advertorial_url(url: str) -> bool:
    """
    Check if URL contains patterns indicating advertorial content.

    Args:
        url: The article URL to check

    Returns:
        True if URL matches advertorial patterns
    """
    if not url:
        return False

    url_lower = url.lower()
    return any(pattern in url_lower for pattern in ADVERTORIAL_URL_PATTERNS)


def has_advertorial_keywords(text: str, threshold: int = 2) -> bool:
    """
    Check if text contains multiple advertorial keywords.

    Args:
        text: The text to check (title, content, etc.)
        threshold: Minimum number of keywords to trigger detection (default: 2)

    Returns:
        True if text contains threshold or more advertorial keywords
    """
    if not text:
        return False

    text_lower = text.lower()
    keyword_count = sum(1 for keyword in ADVERTORIAL_KEYWORDS if keyword in text_lower)
    return keyword_count >= threshold


def is_advertorial(url: str = None, title: str = None, content: str = None) -> tuple[bool, str]:
    """
    Comprehensive check for advertorial content.

    Args:
        url: Article URL
        title: Article title
        content: Article content

    Returns:
        Tuple of (is_advertorial, reason)
    """
    # Check URL patterns first (fastest)
    if url and is_advertorial_url(url):
        return True, "URL pattern match"

    # Check title for advertorial keywords
    if title and has_advertorial_keywords(title, threshold=1):
        # Lower threshold for titles as they're shorter
        return True, "Title keyword match"

    # Check combined title + first 500 chars of content
    if title and content:
        combined_text = f"{title} {content[:500]}"
        if has_advertorial_keywords(combined_text, threshold=2):
            return True, "Multiple keyword matches"

    return False, ""

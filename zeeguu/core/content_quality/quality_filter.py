import newspaper
from langdetect import detect
from zeeguu.core.model import Article, LowQualityTypes
from zeeguu.core.ml_models import is_paywalled, ID_TO_LABEL_PAYWALL

# Feeds that should skip HTML pattern analysis
# These feeds have paywall patterns in their raw HTML (sidebar/footer) but
# still deliver full article content that can be extracted by readability
SKIP_HTML_PATTERN_CHECK_FEEDS = [
    "pourlascience.fr",  # Has paywall patterns but delivers full content via RSS
]

HTML_READ_MORE_PATTERNS = [
    "To continue reading this premium",  # New Scientist
    "Cet article est réservé aux abonnés",  # Le Figaro
    "L'accès à la totalité de l'article est protégé",  # Le Monde
    "Ces informations sont destinées au groupe Bayard",  # 1jour1actu
    "Article réservé aux abonnés"
    # der spiegel
    ,
    "Sie haben keinen Zugang? Jetzt gratis testen!.",
    "Jetzt Gratismonat beginnen",
]

PLAIN_TEXT_PAYWALL_PATTERNS = [
    "Create an account for free access to:",  # New Scientist
    "édition abonné",  # /www.lemonde.fr
    # Politiken, JP, Danish media
    "Allerede abonnent?",
    "Er du abonnent?",
    "Velkommen tilbage. Log ind",
    "Bliv abonnent",
    "få adgang til hele artiklen",
    "Du er godt i gang",
    "Ingen binding",
    "fortsæt med at læse",
    "FOR ABONNENTER",
    # Ing
    "Alternativt kan du købe et abonnement",
    "Zugang zu allen F+ Artikeln",
    # JP
    "For abonnenter",
    "article abonné",
    # Danish media paywalls
    "Læs videre for 1 kr.",
    # Portuguese paywalls
    "artigo exclusivo para assinantes",
    "já é assinante? faça login aqui",
    # Spanish paywalls
    "suscríbete para seguir leyendo",
    # French paywalls
    "pour accéder gratuitement au site (hors contenus exclusifs abonnés)",
    "en vous abonnant, vous accédez",
    "Votre abonnement n'autorise pas la lecture de cet article",
    "Lecture restreinte",
    # Swedish/Danish paywalls
    "som inloggad kan du ta del av flera smarta funktioner",
    "er du allerede prenumerant, logga in för att fortsätta läsa",
    "är du redan prenumerant, logga in",
    "passa på – 0 kr fram till 1 feb, sedan endast 85 kr/mån",
    "ingen bindningstid, säg upp enkelt när du vill",
    "❌der opstod en fejl",
    # English paywalls
    "power up with unlimited access to wired",
    "subscribe today",
]

incomplete_suggesting_terminations = "Read More"

LIVE_BLOG_KIND_OF_PATTERNS = [
    "Lees hier het hele verhaal",
    "Lees hier het hele verhaal",
]


def sufficient_quality_html(html):
    for each in HTML_READ_MORE_PATTERNS:
        if html.find(each) > 0:
            return (
                False,
                f"Incomplete Article (based on HTML analysis). Contains: {each}",
                LowQualityTypes.HTML_PATTERN,
            )
    return True, "", ""


def sufficient_quality_plain_text(text, lang_code=None):
    word_count = len(text.split())
    if word_count < Article.MINIMUM_WORD_COUNT:
        return (
            False,
            f"Too Short ({word_count} words) {text}",
            LowQualityTypes.TOO_SHORT,
        )
    
    if word_count > Article.MAXIMUM_WORD_COUNT:
        return (
            False,
            f"Too Long ({word_count} words) - likely extraction error or excessive content",
            LowQualityTypes.TOO_LONG,
        )

    for each in PLAIN_TEXT_PAYWALL_PATTERNS:
        if text.find(each) >= 0:
            return (
                False,
                f"Incomplete pattern in text: {each}",
                LowQualityTypes.TEXT_PAYWALL_PATTERN,
            )

    if text.endswith(incomplete_suggesting_terminations):
        return (
            False,
            'Ends with "Read More" or similar',
            LowQualityTypes.INCOMPLETE_PATTERN,
        )

    art_lang = detect(text)
    if lang_code is not None and art_lang != lang_code:
        return (
            False,
            f"Article language '{art_lang}', does not match feed language: '{lang_code}'.",
            LowQualityTypes.LANGUAGE_DOES_NOT_MATCH_FEED,
        )

    for each in LIVE_BLOG_KIND_OF_PATTERNS:
        if text.find(each) >= 0:
            return False, "Live blog kind of article", LowQualityTypes.LIVE_BLOG

    paywall_pred = is_paywalled(text)
    if paywall_pred > 0:
        # 0 is Normal Text
        label_found = ID_TO_LABEL_PAYWALL[paywall_pred]
        return (
            False,
            f"ML Prediction was '{label_found}'.",
            LowQualityTypes.ML_PREDICTION,
        )

    return True, "", ""


def _should_skip_html_check(feed_url: str) -> bool:
    """Check if feed should skip HTML pattern analysis."""
    if not feed_url:
        return False
    for domain in SKIP_HTML_PATTERN_CHECK_FEEDS:
        if domain in feed_url:
            return True
    return False


def sufficient_quality(art: newspaper.Article, lang_code=None, feed_url=None) -> tuple[bool, str, str]:
    # Skip HTML check for whitelisted feeds that have paywall patterns
    # in raw HTML but still deliver extractable content
    if not _should_skip_html_check(feed_url):
        res, reason, code = sufficient_quality_html(art.html)
        if not res:
            return False, reason, code

    res, reason, code = sufficient_quality_plain_text(art.text, lang_code)
    if not res:
        return False, reason, code

    return True, "", ""

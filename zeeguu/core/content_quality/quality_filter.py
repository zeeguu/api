import newspaper
from zeeguu.core.model import Article

HTML_READ_MORE_PATTERNS = [
    "To continue reading this premium",  # New Scientist
    "Cet article est réservé aux abonnés",  # Le Figaro
    "L’accès à la totalité de l’article est protégé",  # Le Monde
    "Ces informations sont destinées au groupe Bayard",  # 1jour1actu
    "Article réservé aux abonnés"
    # der spiegel
    ,
    "Sie haben keinen Zugang? Jetzt gratis testen!.",
    "Jetzt Gratismonat beginnen",
]

plain_text_read_more_patterns = [
    "Create an account for free access to:",  # New Scientist
    "édition abonné",  # /www.lemonde.fr
    # Politiken
    "Allerede abonnent? Login",
    "FOR ABONNENTER",
]

incomplete_suggesting_terminations = "Read More"

LIVE_BLOG_KIND_OF_PATTERNS = [
    "Lees hier het hele verhaal",
    "Lees hier het hele verhaal"
]


def sufficient_quality_html(html):
    for each in HTML_READ_MORE_PATTERNS:
        if html.find(each) > 0:
            return (
                False,
                f"Incomplete Article (based on HTML analysis). Contains: {each}",
            )
    return True, ""


def sufficient_quality_plain_text(text):
    word_count = len(text.split(" "))

    if word_count < Article.MINIMUM_WORD_COUNT:
        return False, f"Too Short ({word_count} words) {text}"

    for each in plain_text_read_more_patterns:
        if text.find(each) >= 0:
            return False, f"Incomplete pattern in text: {each}"

    if text.endswith(incomplete_suggesting_terminations):
        return False, 'Ends with "Read More" or similar'

    for each in LIVE_BLOG_KIND_OF_PATTERNS:
        if text.find(each) >= 0:
            return False, "Live blog kind of article"

    return True, ""


def sufficient_quality(art: newspaper.Article) -> (bool, str):
    res, reason = sufficient_quality_html(art.html)
    if not res:
        return False, reason
    res, reason = sufficient_quality_plain_text(art.text)
    if not res:
        return False, reason

    return True, ""

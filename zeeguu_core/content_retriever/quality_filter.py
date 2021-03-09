import zeeguu_core
import newspaper
from zeeguu_core.model import Article

html_read_more_patterns = [
    "To continue reading this premium"  # New Scientist
    , "Cet article est réservé aux abonnés"  # Le Figaro
    , "L’accès à la totalité de l’article est protégé"  # Le Monde
    , "Ces informations sont destinées au groupe Bayard"  # 1jour1actu
    , "Article réservé aux abonnés"

    # der spiegel
    , "Sie haben keinen Zugang? Jetzt gratis testen!."
    , "Jetzt Gratismonat beginnen"
]

plain_text_read_more_patterns = [
    "Create an account for free access to:",  # New Scientist
    "édition abonné"  # /www.lemonde.fr
]

incomplete_suggesting_terminations = (
    "Read More"
)


def sufficient_quality(art: newspaper.Article) -> (bool, str):
    """

        :param art:

    :return:
        bool: True/False
        str: reason if false
    """
    for each in html_read_more_patterns:
        if art.html.find(each) > 0:
            return False, f"Incomplete Article (based on HTML analysis). Contains: {each}"

    word_count = len(art.text.split(" "))

    if word_count < Article.MINIMUM_WORD_COUNT:
        return False, f"Too Short ({word_count} words) {art.text}"

    for each in plain_text_read_more_patterns:
        if art.text.find(each) >= 0:
            return False, f"Incomplete pattern in text: {each}"

    if art.text.endswith(incomplete_suggesting_terminations):
        return False, 'Ends with "Read More" or similar'

    return True, ""

import zeeguu.core
from zeeguu.core.model import Article, Language
from nltk.tokenize import sent_tokenize
import os
import json

JUNK_PATTERNS_TO_REMOVE = [
    "\nAdvertisement\n",
    "\ntrue\n",
    "Automatisk oplæsning\n",
    "Som registreret bruger kan du overvåge emner og journalister og modtage nyhederne i din indbakke og følge din nyhedsstrøm på Finans.",
    # L'Express, October 19
    "\nOffre limitée. 2 mois pour 1€ sans engagement\n",
    "\nJe m'abonne\n",
    # Hoff Post
    "À voir également sur le HuffPost",
    "À voir également sur Le HuffPost",
    #     Le Monde
    "Le Monde avec AFP",
    "Vous pouvez lire Le Monde sur un seul appareil à la fois",
    "Ce message s'affichera sur l'autre appareil.",
    "Découvrir les offres multicomptes",
    "Pour plus d'informations, merci de contacter notre service commercial.",
    #     dk
    "Artiklen fortsætter efter annoncen",
    # French cookie/ad notices
    "Passer la publicité",
    "La suite après cette publicité",
    "Quel plaisir de vous retrouver, avant d'accéder à l'équipe, merci d'accepter les cookies.",
    "Accepter les cookies et accéder à l'équipe gratuitement",
    "L'équipe, les sociétés de son groupe et utilisent des cookies",
    "et pourront être modifiées à tout moment via le menu",
    "Cela nous permet de vous afficher de la publicité personnalisée",
    "En cas de refus, navigation et fonctionnalités seront limitées sur le site.",
    "Vos préférences s'appliqueront uniquement à nos sites",
    "Plus d'informations : politique de confidentialité.",
    "L'équipe shopping du figaro est indépendante de la rédaction.",
    # German affiliate links
    "Preis kann jetzt höher sein.",
    "Der preis für dich bleibt gleich.",
    "Mehr erfahren.",
    "Der preis für dich bleibt dabei unverändert.",
    "Diese affiliate-links sind durch ein",
    "symbol gekennzeichnet.",
    "Wenn du über diese links einkaufst, erhalten wir eine provision",
    "Das hilft unserer arbeit.",
    "Hat dir der beitrag gefallen?",
    "Folge uns auf msn und google news",
    # Portuguese editorial disclaimers
    "Os textos nesta secção refletem a opinião pessoal dos autores.",
    "Não representam a visão nem espelham o seu posicionamento editorial.",
    # Swedish account notices
    "Du vet väl att du kan skapa ett gratiskonto på dn?",
    # Italian newsletter prompts
    "Vuoi ricevere tutto il meglio di vogue italia nella tua casella di posta?",
    "Iscriviti alla newsletter",
    "Notizie e approfondimenti sugli avvenimenti politici",
    "Leggi anche:",
    # Greek boilerplate
    "φόρτωση text-to-speech",
    "ακολουθήστε το techmaniacs.gr",
    "ένας ακόμα τρόπος να μαθαίνετε τα πάντα πρώτοι",
    # French navigation
    "a lire aussi",
    "à lire aussi",
]

JUNK_PATTERNS_DATA_FOLDER = os.path.dirname(__file__)
JUNK_COUNT_FILEPATH = os.path.join(
    JUNK_PATTERNS_DATA_FOLDER, "data", "junk_patterns_found.json"
)

with open(JUNK_COUNT_FILEPATH, "r", encoding="utf-8") as f:
    json_data = json.load(f)
    JUNK_COUNT_PATTERNS = [sent for lang in json_data.values() for sent in lang]

JUNK_PREFIXES = [
    "Der er ikke oplæsning af denne artikel, så den oplæses derfor med maskinstemme."
]

"""

    Sometimes newspaper/readability still leaves some individual fragments
    in the article.text.


:param text:
:return:
"""


def normalize_sent(text: str):
    return text.lower().strip()


def filter_noise_patterns(
    article, sent_filter_set, crawl_report=None, feed=None, url=None
):
    clean_artcile = ""
    for paragraph in article.split("\n\n"):
        clean_paragraph = ""
        is_prev_skip = False
        for sent in sent_tokenize(paragraph):
            if is_prev_skip and len(sent) <= 10:
                print("Skipped (Prev Skipped and Short!): ", sent)
                if crawl_report is not None:
                    crawl_report.add_sent_removed(feed, sent, url)
                continue
            else:
                is_prev_skip = False
            if normalize_sent(sent) in sent_filter_set:
                print("Skipped (Repetitive): ", sent)
                if crawl_report is not None:
                    crawl_report.add_sent_removed(feed, sent, url)
                is_prev_skip = True
                continue
            clean_paragraph += sent + " "
        if len(clean_paragraph) < 10:
            continue
        clean_artcile += clean_paragraph + "\n\n"
    return clean_artcile.strip()


def cleanup_non_content_bits_w_crawl_report(text: str, crawl_report, feed, url) -> str:
    if text is None:
        return None
    new_text = text
    new_text = filter_noise_patterns(
        text, set(JUNK_COUNT_PATTERNS), crawl_report, feed, url
    )
    for junk_pattern in JUNK_PATTERNS_TO_REMOVE:
        cleaned = new_text.replace(junk_pattern, "")

        if cleaned != new_text:
            crawl_report.add_sent_removed(feed, junk_pattern, url)
            print(f"- cleaned: {junk_pattern}")
            new_text = cleaned

    clean_text = ""
    for junk_prefix in JUNK_PREFIXES:
        for each in new_text.split("\n"):
            if each.startswith(junk_prefix):
                print(">>>> dropping the Paragraph: " + each)
                crawl_report.add_sent_removed(feed, junk_pattern, url)
                continue
            clean_text += each + "\n"

    return clean_text


def cleanup_non_content_bits(text: str):
    new_text = text
    new_text = filter_noise_patterns(text, set(JUNK_COUNT_PATTERNS))

    for junk_pattern in JUNK_PATTERNS_TO_REMOVE:
        cleaned = new_text.replace(junk_pattern, "")

        if cleaned != new_text:
            print(f"- cleaned: {junk_pattern}")
            new_text = cleaned

    clean_text = ""
    for junk_prefix in JUNK_PREFIXES:
        for each in new_text.split("\n"):
            if each.startswith(junk_prefix):
                print(">>>> dropping the Paragraph: " + each)
                continue
            clean_text += each + "\n"

    return clean_text


def cleanup_all_articles_in_language(language_code):
    db_session = zeeguu.core.model.db.session
    language_id = Language.find(language_code).id
    all_articles = Article.query.filter_by(language_id=language_id).all()
    for each in all_articles:
        cleaned_content = cleanup_non_content_bits(each.get_content())
        if cleaned_content != each.get_content():
            each.update_content(db_session, content=cleaned_content, commit=False)
            print(each.title + "\n\n")
    db_session.commit()

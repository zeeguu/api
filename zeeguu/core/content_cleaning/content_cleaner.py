import zeeguu.core
from zeeguu.core.model import Article, Language

JUNK_PATTERNS_TO_REMOVE = [

    "\nAdvertisement\n",
    "\ntrue\n",
    "Automatisk oplæsning\n",
    "Der er ikke oplæsning af denne artikel, så den oplæses derfor med maskinstemme. Kontakt os gerne på automatiskoplaesning@pol.dk, hvis du hører ord, hvis udtale kan forbedres. Du kan også hjælpe ved at udfylde spørgeskemaet herunder, hvor vi spørger, hvordan du har oplevet den automatiske oplæsning. Spørgeskema om automatisk oplæsning",
    "Som registreret bruger kan du overvåge emner og journalister og modtage nyhederne i din indbakke og følge din nyhedsstrøm på Finans.",

    # L'Express, October 19
    "\nOffre limitée. 2 mois pour 1€ sans engagement\n",
    "\nJe m'abonne\n",
    "À voir également sur le HuffPost",
    "À voir également sur Le HuffPost",

#     Le Monde
    "Le Monde avec AFP",
    "Vous pouvez lire Le Monde sur un seul appareil à la fois",
    "Ce message s’affichera sur l’autre appareil.",
    "Découvrir les offres multicomptes",
    "Votre abonnement n’autorise pas la lecture de cet article",
    "Lecture restreinte",
    "Pour plus d’informations, merci de contacter notre service commercial."

]


def cleanup_non_content_bits(text: str):
    """

        Sometimes newspaper still leaves some individual fragments
        in the article.text.


    :param text:
    :return:
    """
    new_text = text

    for junk_pattern in JUNK_PATTERNS_TO_REMOVE:
        cleaned = new_text.replace(junk_pattern, "")

        if cleaned != new_text:
            print(f"- cleaned: {junk_pattern}")
            new_text = cleaned

    return new_text


def cleanup_all_articles_in_language(language_code):
    language_id = Language.find(language_code).id
    all_articles = Article.query.filter_by(language_id=language_id).all()
    for each in all_articles:
        cleaned_content = cleanup_non_content_bits(each.content)
        if cleaned_content != each.content:
            each.content = cleaned_content
            zeeguu.core.db.session.add(each)
            print(each.title + "\n\n")
    zeeguu.core.db.session.commit()

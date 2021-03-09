import zeeguu_core
from zeeguu_core.model import Article, Language

JUNK_PATTERNS = [

    "\nAdvertisement\n",
    "\ntrue\n",
    "Automatisk oplæsning\n",
    "Der er ikke oplæsning af denne artikel, så den oplæses derfor med maskinstemme. Kontakt os gerne på automatiskoplaesning@pol.dk, hvis du hører ord, hvis udtale kan forbedres. Du kan også hjælpe ved at udfylde spørgeskemaet herunder, hvor vi spørger, hvordan du har oplevet den automatiske oplæsning. Spørgeskema om automatisk oplæsning",
    "Som registreret bruger kan du overvåge emner og journalister og modtage nyhederne i din indbakke og følge din nyhedsstrøm på Finans.",

]


def cleanup_non_content_bits(text: str):
    """

        Sometimes newspaper still leaves some individual fragments
        in the article.text.


    :param text:
    :return:
    """
    new_text = text

    for junk_pattern in JUNK_PATTERNS:
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
            zeeguu_core.db.session.add(each)
            print(each.title + "\n\n")
    zeeguu_core.db.session.commit()

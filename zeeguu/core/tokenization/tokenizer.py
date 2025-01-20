from zeeguu.core.tokenization.token import Token
from zeeguu.core.model.language import Language
import re
import nltk

NLTK_SUPPORTED_LANGUAGES = set(
    [
        "czech",
        "danish",
        "dutch",
        "english",
        "estonian",
        "finnish",
        "french",
        "german",
        "greek",
        "italian",
        "norwegian",
        "polish",
        "portuguese",
        "russian",
        "slovene",
        "spanish",
        "swedish",
        "turkish",
    ]
)

# Compile all regex before hand to speed up matching.

PARAGRAPH_DELIMITER = re.compile(r"\n\n+")
APOSTROPHE_BEFORE_WORD = re.compile(r" (')([\w]+)")


def split_into_paragraphs(text):
    """
    We expect articles to have been parsed by readability, so they are often composed of
    paragraphs seperated by two newlines. To avoid cases where there are multiple newlines,
    we consider a paragraph as long as there are continuous newlines.
    """
    return PARAGRAPH_DELIMITER.split(text)


def text_preprocessing(text: str):
    """
    Preprocesses the text by replacing some apostraphe characters to a standard one.
    """
    # For French & Italian, the tokenizer doesn't recognize ’, but it works
    # if ' is used.
    text = text.replace("’", "'")
    # For Spanish "¿" is attached to the first word, so we need to add a space
    text = text.replace("¿", "¿ ")
    # For cases where there is a quote such as: "tú dices: 'Mira, qué interesante'."
    # In this case we want the ' to be separated from the word.
    text = APOSTROPHE_BEFORE_WORD.sub(lambda m: f"{m.group(1)} {m.group(2)}", text)
    return text


def replace_email_url_with_placeholder(text: str):
    """
    The tokenizer has issues tokenizing emails and urls.
    To avoid this, we replace them with a placeholder:
    _EMAIL_ and _URL_
    """

    def _has_protocol(url_match):
        return url_match[2] != ""

    urls = Token.URL_REGEX.findall(text)
    for url in urls:
        text = text.replace(url[0], "_URL_ ")
    emails = Token.EMAIL_REGEX.findall(text)
    for email in emails:
        text = text.replace(email, "_EMAIL_ ")

    url_links = [url[0] if _has_protocol(url) else "https://" + url[0] for url in urls]

    return (
        text,
        emails,
        url_links,
    )


def is_nltk_supported_language(language: Language):
    return language.name.lower() in NLTK_SUPPORTED_LANGUAGES


def _get_token(t, par_i, sent_i, w_i, email, url, as_serializable_dictionary):
    if t == "_EMAIL_":
        t = email.pop(0)
    if t == "_URL_":
        t = url.pop(0)

    token = Token(t, par_i, sent_i, w_i)
    return token.as_serializable_dictionary() if as_serializable_dictionary else token


def tokenize_text(text: str, language: Language, as_serializable_dictionary=True):

    if not is_nltk_supported_language(language):
        print(
            f"Failed 'tokenize_text' for language: '{language.name.lower()}', defaulted to 'english'"
        )
        language = Language.find("en")

    text = text_preprocessing(text)
    text, email, url = replace_email_url_with_placeholder(text)

    tokens = [
        [
            [
                (
                    _get_token(
                        w, par_i, sent_i, w_i, email, url, as_serializable_dictionary
                    )
                )
                for w_i, w in enumerate(
                    nltk.tokenize.word_tokenize(sent, language=language.name.lower())
                )
            ]
            for sent_i, sent in enumerate(
                sent_tokenizer_text(paragraph, language=language)
            )
        ]
        for par_i, paragraph in enumerate(split_into_paragraphs(text))
    ]
    return tokens


def tokenize_text_flat_array(
    text: str, language: Language, as_serializable_dictionary=True
):
    if not is_nltk_supported_language(language):
        print(
            f"Failed 'tokenize_text_flat_array' for language: '{language.name.lower()}', defaulted to 'english'"
        )
        language = Language.find("en")

    text = text_preprocessing(text)
    text, email, url = replace_email_url_with_placeholder(text)

    tokens = [
        _get_token(w, par_i, sent_i, w_i, email, url, as_serializable_dictionary)
        for par_i, paragraph in enumerate(split_into_paragraphs(text))
        for sent_i, sent in enumerate(sent_tokenizer_text(paragraph, language=language))
        for w_i, w in enumerate(
            nltk.tokenize.word_tokenize(sent, language=language.name.lower())
        )
    ]
    return tokens


def sent_tokenizer_text(text: str, language: Language):
    if not is_nltk_supported_language(language):
        print(
            f"Failed 'sent_tokenize' for language: '{language.name.lower()}', defaulted to 'english'",
        )
        language = Language.find("en")
    return nltk.tokenize.sent_tokenize(text, language=language.name.lower())

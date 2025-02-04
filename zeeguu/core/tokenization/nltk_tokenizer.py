from zeeguu.core.tokenization.token import Token
from zeeguu.core.tokenization.zeeguu_tokenizer import ZeeguuTokenizer, TokenizerModel
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

APOSTROPHE_BEFORE_WORD = re.compile(r" (')([\w]+)")

URL_PLACEHOLDER = "#URL#"
EMAIL_PLACEHOLDER = "#EMAIL#"


class NLTKTokenizer(ZeeguuTokenizer):
    def __init__(self, language: Language):
        super().__init__(language, TokenizerModel.NLTK)

    def text_preprocessing(self, text: str):
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

    def is_language_supported(self, language: Language):
        return language.name.lower() in NLTK_SUPPORTED_LANGUAGES

    def replace_email_url_with_placeholder(self, text: str):
        """
        The tokenizer has issues tokenizing emails and urls.
        To avoid this, we replace them with a placeholder:
            URL_PLACEHOLDER and EMAIL_PLACEHOLDER
        """

        def _has_protocol(url_match):
            return url_match[2] != ""

        emails = Token.EMAIL_REGEX.findall(text)
        for email in emails:
            text = text.replace(email, f"{EMAIL_PLACEHOLDER} ")
        urls = Token.URL_REGEX.findall(text)
        for url in urls:
            text = text.replace(url[0], f"{URL_PLACEHOLDER} ")

        url_links = [
            url[0] if _has_protocol(url) else "https://" + url[0] for url in urls
        ]

        return (
            text,
            emails,
            url_links,
        )

    def _get_token(
        self,
        t,
        par_i,
        sent_i,
        w_i,
        has_space,
        email,
        url,
        as_serializable_dictionary,
        pos=None,
    ):
        if t == EMAIL_PLACEHOLDER:
            t = email.pop(0)
        if t == URL_PLACEHOLDER:
            t = url.pop(0)

        token = Token(t, par_i, sent_i, w_i, has_space, pos)
        if as_serializable_dictionary:
            return token.as_serializable_dictionary()
        return token

    def get_sentences(self, text: str):
        language = self.language
        if not self.is_language_supported(language):
            print(
                f"Failed 'sent_tokenize' for language: '{language.name.lower()}', defaulted to 'english'",
            )
            language = Language.find("en")
        return nltk.tokenize.sent_tokenize(text, language=language.name.lower())

    def tokenize_text(
        self, text: str, as_serializable_dictionary: bool = True, flatten: bool = True
    ):
        language = self.language
        if not self.is_language_supported(language):
            print(
                f"Failed 'tokenize_text' for language: '{self.language.name.lower()}', defaulted to 'english'"
            )
            language = Language.find("en")

        text = self.text_preprocessing(text)
        text, email, url = self.replace_email_url_with_placeholder(text)
        # Using list enumration for slightly improved performance.
        tokens = [
            [
                [
                    (
                        self._get_token(
                            w,
                            par_i,
                            sent_i,
                            w_i,
                            True,
                            email,
                            url,
                            as_serializable_dictionary,
                        )
                    )
                    for w_i, w in enumerate(
                        nltk.tokenize.word_tokenize(
                            sent, language=language.name.lower()
                        )
                    )
                ]
                for sent_i, sent in enumerate(self.get_sentences(paragraph))
            ]
            for par_i, paragraph in enumerate(
                ZeeguuTokenizer.split_into_paragraphs(text)
            )
        ]
        if flatten:
            tokens = self._flatten_paragraph_list(tokens)
        return tokens

from zeeguu.core.tokenization.token import Token
from zeeguu.core.model.language import Language
import re
import nltk
import stanza
from enum import IntEnum


class TokenizerModel(IntEnum):
    NLTK = 1
    STANZA_TOKEN_ONLY = 2
    STANZA_TOKEN_POS = 3


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

PARAGRAPH_DELIMITER = re.compile(r"((\s?)+\\n+)")
APOSTROPHE_BEFORE_WORD = re.compile(r" (')([\w]+)")
URL_PLACEHOLDER = "#URL#"
EMAIL_PLACEHOLDER = "#EMAIL#"


class ZeeguuTokenizer:
    STANZA_MODELS = set(
        [TokenizerModel.STANZA_TOKEN_ONLY, TokenizerModel.STANZA_TOKEN_POS]
    )
    # We cache the models to avoid having to re-initialize pipelines everytime.
    # Once the model is loaded it's kept in memory for later use.
    CACHED_NLP_PIPELINES = {}

    def _get_stanza_processor(model: TokenizerModel):
        if model == TokenizerModel.STANZA_TOKEN_ONLY:
            return "tokenize"
        elif model == TokenizerModel.STANZA_TOKEN_POS:
            return "tokenize,pos"
        return ""

    def __init__(self, language: Language, model: TokenizerModel):
        self.language = language
        self.model_type = model
        self.nlp_pipeline = None

        if self.model_type in ZeeguuTokenizer.STANZA_MODELS:
            # Store used models.
            key = (self.language.code, self.model_type)
            if key not in ZeeguuTokenizer.CACHED_NLP_PIPELINES:
                pipeline = stanza.Pipeline(
                    lang=self.language.code,
                    processors=ZeeguuTokenizer._get_stanza_processor(model),
                    download_method=None,
                )
                ZeeguuTokenizer.CACHED_NLP_PIPELINES[key] = pipeline
            else:
                print("Pipeline cache hit! ", key)
            self.nlp_pipeline = ZeeguuTokenizer.CACHED_NLP_PIPELINES[key]

    @classmethod
    def split_into_paragraphs(cls, text):
        """
        We expect articles to have been parsed by readability, so they are often composed of
        paragraphs seperated by two newlines. To avoid cases where there are multiple newlines,
        we consider a paragraph as long as there are continuous newlines.

        For this reason, this can be called without creating a tokenizer object.
        """
        return PARAGRAPH_DELIMITER.split(text)

    def _nltk_text_preprocessing(self, text: str):
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

    def is_nltk_supported_language(self, language: Language):
        return language.name.lower() in NLTK_SUPPORTED_LANGUAGES

    def replace_email_url_with_placeholder(self, text: str):
        """
        The tokenizer has issues tokenizing emails and urls.
        To avoid this, we replace them with a placeholder:
        _EMAIL_ and _URL_
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

    def _flatten_paragraph_list(self, paragraphs: list):
        flatten_tokens = []
        for p in paragraphs:
            for s in p:
                flatten_tokens.extend(s)
        return flatten_tokens

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
        return (
            token.as_serializable_dictionary() if as_serializable_dictionary else token
        )

    def _nltk_sentencizer_text(self, text: str):
        language = self.language
        if not self.is_nltk_supported_language(language):
            print(
                f"Failed 'sent_tokenize' for language: '{language.name.lower()}', defaulted to 'english'",
            )
            language = Language.find("en")
        return nltk.tokenize.sent_tokenize(text, language=language.name.lower())

    def _nltk_tokenization(
        self,
        text: str,
        as_serializable_dictionary,
        flatten,
    ):
        language = self.language
        if not self.is_nltk_supported_language(language):
            print(
                f"Failed 'tokenize_text' for language: '{self.language.name.lower()}', defaulted to 'english'"
            )
            language = Language.find("en")

        text = self._nltk_text_preprocessing(text)
        text, email, url = self.replace_email_url_with_placeholder(text)
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
                for sent_i, sent in enumerate(self._nltk_sentencizer_text(paragraph))
            ]
            for par_i, paragraph in enumerate(
                ZeeguuTokenizer.split_into_paragraphs(text)
            )
        ]
        if flatten:
            tokens = self._flatten_paragraph_list(tokens)
        return tokens

    def _stanza_tokenization(self, text: str, as_serializable_dictionary, flatten):
        result = []
        doc = self.nlp_pipeline(text)
        current_paragraph = []
        s_i = 0
        for sentence in doc.sentences:
            sent_list = []
            is_new_paragraph = False
            for t_i, token in enumerate(sentence.tokens):
                t_dict = token.to_dict()
                if len(t_dict) > 1:
                    # We have a composed token (of multiple tokens)
                    # The first is the composed token
                    t_dict = t_dict[1:]
                for t_details in t_dict:
                    has_space = not ("SpaceAfter=No" in t_details.get("misc", ""))
                    sent_list.append(
                        self._get_token(
                            t_details["text"],
                            len(result),
                            s_i,
                            t_i,
                            has_space,
                            [],
                            [],
                            as_serializable_dictionary,
                            pos=t_details.get("upos", None),
                        )
                    )
                    if PARAGRAPH_DELIMITER.search(t_details.get("misc", "")):
                        is_new_paragraph = True
            current_paragraph.append(sent_list)
            s_i += 1
            if is_new_paragraph:
                result.append(current_paragraph)
                current_paragraph = []
                s_i = 0
        result.append(current_paragraph)

        if flatten:
            result = self._flatten_paragraph_list(result)
        return result

    def _stanza_sentencizer(self, text: str):
        doc = self.nlp_pipeline(text)
        return [
            " ".join([token.text for token in sent.tokens]) for sent in doc.sentences
        ]

    def tokenize_text(self, text: str, as_serializable_dictionary=True, flatten=True):
        """
        Returns a tokenize text as a list of pargraphs, containing a list of sentences
        containing a list of tokens.

        - as_serializable_dictionary:boolean - determines if the objects are returned
        as json dictionaries that can be used by the frontend.
        - flatten:boolean - determines if the list should be sent as an array or a list
        containing paragraphs, composed of a list of sentences with tokens.
        """
        if self.nlp_pipeline:
            return self._stanza_tokenization(text, as_serializable_dictionary, flatten)
        else:
            return self._nltk_tokenization(text, as_serializable_dictionary, flatten)

    def get_sentences(self, text: str):
        if self.nlp_pipeline:
            return self._stanza_sentencizer(text)
        else:
            return self._nltk_sentencizer_text(text)

from zeeguu.core.model.language import Language
from enum import IntEnum
import re


class TokenizerModel(IntEnum):
    NLTK = 1
    STANZA_TOKEN_ONLY = 2
    STANZA_TOKEN_POS = 3


PARAGRAPH_DELIMITER = re.compile(r"\n\n+")


class ZeeguuTokenizer:
    def __init__(self, language: Language, model: TokenizerModel):
        self.language = language
        self.model_type = model

    @classmethod
    def split_into_paragraphs(cls, text):
        """
        We expect articles to have been parsed by readability, so they are often composed of
        paragraphs seperated by two newlines. To avoid cases where there are multiple newlines,
        we consider a paragraph as long as there are continuous newlines.

        For this reason, this can be called without creating a tokenizer object.
        """
        return PARAGRAPH_DELIMITER.split(text)

    def is_language_supported(self, language: Language):
        raise NotImplementedError

    def _flatten_paragraph_list(self, paragraphs: list):
        flatten_tokens = []
        for p in paragraphs:
            for s in p:
                flatten_tokens.extend(s)
        return flatten_tokens

    def sentencizer(self, text: str):
        raise NotImplementedError

    def tokenize_text(
        self,
        text: str,
        as_serializable_dictionary=True,
        flatten=True,
        start_token_i: int = 0,
        start_sentence_i: int = 0,
        start_paragraph_i: int = 0,
    ):
        """
        Returns a tokenize text as a list of pargraphs, containing a list of sentences
        containing a list of tokens.

        - as_serializable_dictionary:boolean - determines if the objects are returned
        as json dictionaries that can be used by the frontend.
        - flatten:boolean - determines if the list should be sent as an array or a list
        containing paragraphs, composed of a list of sentences with tokens.
        """
        raise NotImplementedError

    def get_sentences(self, text: str):
        raise NotImplementedError

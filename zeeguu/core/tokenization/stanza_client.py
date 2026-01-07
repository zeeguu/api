"""
HTTP client for Stanza tokenization microservice.

This client provides the same interface as StanzaTokenizer but delegates
actual tokenization to the Stanza service via HTTP.

If the service is unavailable, falls back to local StanzaTokenizer.
"""

import os
import logging
import requests
from zeeguu.core.model.language import Language
from zeeguu.core.tokenization.zeeguu_tokenizer import ZeeguuTokenizer, TokenizerModel
from zeeguu.core.tokenization.token import Token

logger = logging.getLogger(__name__)

# Service URL from environment variable
STANZA_SERVICE_URL = os.environ.get("STANZA_SERVICE_URL", "")

# Map TokenizerModel enum to service model strings
MODEL_TYPE_MAP = {
    TokenizerModel.STANZA_TOKEN_ONLY: "token_only",
    TokenizerModel.STANZA_TOKEN_POS: "token_pos",
    TokenizerModel.STANZA_TOKEN_POS_DEP: "token_pos_dep",
}

# Request timeout - tokenization should be fast, but allow some buffer for long articles
REQUEST_TIMEOUT = 30  # seconds


def _get_local_tokenizer(language, model):
    """Get local StanzaTokenizer as fallback."""
    from .stanza_tokenizer import StanzaTokenizer

    return StanzaTokenizer(language, model)


class StanzaServiceClient(ZeeguuTokenizer):
    """
    HTTP client for Stanza service.

    Provides the same interface as StanzaTokenizer but makes HTTP calls
    to the Stanza microservice instead of loading models locally.
    """

    def __init__(self, language: Language, model: TokenizerModel):
        super().__init__(language, model)
        self.service_url = STANZA_SERVICE_URL
        self.model_string = MODEL_TYPE_MAP.get(model, "token_pos_dep")

        if not self.service_url:
            raise ValueError(
                "STANZA_SERVICE_URL environment variable not set. "
                "Set it to the Stanza service URL (e.g., http://stanza:5001)"
            )

    def is_language_supported(self, language: Language):
        return language.code in Language.CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED

    def tokenize_text(
        self,
        text: str,
        as_serializable_dictionary: bool = True,
        flatten: bool = True,
        start_token_i: int = 0,
        start_sentence_i: int = 0,
        start_paragraph_i: int = 0,
    ):
        """
        Tokenize text via Stanza service.

        Returns tokenized text as list of token dictionaries (if as_serializable_dictionary=True)
        or Token objects. Structure depends on flatten parameter.

        Falls back to local StanzaTokenizer if service is unavailable.
        """
        if start_token_i is None:
            start_token_i = 0
        if start_sentence_i is None:
            start_sentence_i = 0
        if start_paragraph_i is None:
            start_paragraph_i = 0

        if not text:
            return []

        try:
            response = requests.post(
                f"{self.service_url}/tokenize",
                json={
                    "text": text,
                    "language": self.language.code,
                    "model": self.model_string,
                    "flatten": flatten,
                    "start_token_i": start_token_i,
                    "start_sentence_i": start_sentence_i,
                    "start_paragraph_i": start_paragraph_i,
                },
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            print("---->>> Stanza Service returned successfully!")
        except requests.RequestException as e:
            logger.warning(f"Stanza service failed, falling back to local: {e}")
            local_tokenizer = _get_local_tokenizer(self.language, self.model_type)
            return local_tokenizer.tokenize_text(
                text,
                as_serializable_dictionary,
                flatten,
                start_token_i,
                start_sentence_i,
                start_paragraph_i,
            )

        tokens_data = data.get("tokens", [])

        if flatten:
            # Flat list of tokens
            if as_serializable_dictionary:
                return tokens_data
            else:
                return [self._dict_to_token(t) for t in tokens_data]
        else:
            # Nested structure: paragraphs > sentences > tokens
            if as_serializable_dictionary:
                return tokens_data
            else:
                return [
                    [[self._dict_to_token(t) for t in sent] for sent in para]
                    for para in tokens_data
                ]

    def get_sentences(self, text: str):
        """Extract sentences from text via Stanza service."""
        if not text:
            return []

        try:
            response = requests.post(
                f"{self.service_url}/sentences",
                json={
                    "text": text,
                    "language": self.language.code,
                    "model": self.model_string,
                },
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("sentences", [])
        except requests.RequestException as e:
            logger.warning(
                f"Stanza service failed for get_sentences, falling back to local: {e}"
            )
            local_tokenizer = _get_local_tokenizer(self.language, self.model_type)
            return local_tokenizer.get_sentences(text)

    def _dict_to_token(self, token_dict):
        """Convert token dictionary from service to Token object."""
        return Token(
            text=token_dict["text"],
            par_i=token_dict.get("par_i"),
            sent_i=token_dict.get("sent_i"),
            token_i=token_dict.get("token_i"),
            has_space=token_dict.get("has_space"),
            pos=token_dict.get("pos"),
            dep=token_dict.get("dep"),
            head=token_dict.get("head"),
            lemma=token_dict.get("lemma"),
        )

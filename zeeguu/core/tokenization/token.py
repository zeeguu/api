import re
from string import punctuation


class Token:
    PUNCTUATION = "»«" + punctuation + "–—“‘”“’„¿"
    LEFT_PUNCTUATION = "«<({#„¿[“"
    RIGHT_PUNCTUATION = "»>)}]”"
    NUM_REGEX = re.compile(r"[0-9]+(\.|,)*[0-9]*")

    # I started from a generated Regex from Co-Pilot and then tested it
    # against a variety of reandom generated links. Generally it seems to work fine,
    # but not likely to be perfect in all situations.
    EMAIL_REGEX = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
    URL_REGEX = re.compile(
        r"(((http|https)://)?(www\.)?([a-zA-Z0-9@\-/\.]+\.[a-z]{1,4}/([a-zA-Z0-9?=\.&#/]+)?)+)"
    )

    @classmethod
    def is_like_email(cls, text):
        return Token.EMAIL_REGEX.match(text) is not None

    @classmethod
    def is_like_url(cls, text):
        return Token.URL_REGEX.match(text) is not None

    @classmethod
    def is_punctuation(cls, text):
        return text in Token.PUNCTUATION or text == "..."

    @classmethod
    def _token_punctuation_processing(cls, text):
        """
        The tokenizer alters the text, so we need to revert some of the changes
        to allow the frontend an easier time to render the text.
        """
        text = text.replace("``", '"')
        text = text.replace("''", '"')
        return text

    def __init__(self, text, par_i=None, sent_i=None, token_i=None):
        """
        sent_i - the sentence in the overall text.
        token_i - the index of the token in the original sentence.
        """
        self.text = Token._token_punctuation_processing(text)
        self.is_sent_start = token_i == 0
        self.is_punct = Token.is_punctuation(self.text)
        self.is_left_punct = text in Token.LEFT_PUNCTUATION
        self.is_right_punct = text in Token.RIGHT_PUNCTUATION
        self.par_i = par_i
        self.sent_i = sent_i
        self.token_i = token_i
        self.is_like_email = Token.is_like_email(text)
        self.is_like_url = Token.is_like_url(text)
        self.is_like_num = Token.NUM_REGEX.match(text) is not None

    def __repr__(self):
        return self.text

    def as_serializable_dictionary(self):
        return {
            "text": self.text,
            "is_sent_start": self.is_sent_start,
            "is_punct": self.is_punct,
            "is_left_punct": self.is_left_punct,
            "is_right_punct": self.is_right_punct,
            "is_like_num": self.is_like_num,
            "sent_i": self.sent_i,
            "token_i": self.token_i,
            "paragraph_i": self.par_i,
            "is_like_email": self.is_like_email,
            "is_like_url": self.is_like_url,
        }

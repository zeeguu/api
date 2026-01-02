import re
from string import punctuation


def match_is_string(result, s):
    return result is not None and result.group(0) == s


class Token:
    PUNCTUATION = "»«" + punctuation + "–—“‘”“’„¿»«"
    SYMBOLS = "©€£$#&@<=>§¢¥¤®º"
    LEFT_PUNCTUATION = "({#„¿[“"
    RIGHT_PUNCTUATION = ")}]”"
    NUM_REGEX = re.compile(r"^([0-9]+(\.|,)*[0-9]*)+$")

    # I started from a generated Regex from Co-Pilot and then tested it
    # against a variety of reandom generated links. Generally it seems to work fine,
    # but not likely to be perfect in all situations.
    EMAIL_REGEX = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{1,4}$)")
    URL_REGEX = re.compile(
        r"(((http|https)://)?(www\.)?([a-zA-Z0-9@\-/\.]+\.[a-z]{2,4}/?([a-zA-Z0-9?=&#/\.]+^\.)?)+)"
    )

    @classmethod
    def is_like_email(cls, text):
        result = Token.EMAIL_REGEX.match(text)
        return match_is_string(result, text)

    @classmethod
    def is_like_url(cls, text):
        result = Token.URL_REGEX.match(text)
        return match_is_string(result, text)

    @classmethod
    def is_like_symbols(cls, text):
        return text in Token.SYMBOLS

    @classmethod
    def is_punctuation(cls, text):
        return text in Token.PUNCTUATION or text == "..." or text == "…"

    @classmethod
    def _token_punctuation_processing(cls, text):
        """
        The tokenizer alters the text, so we need to revert some of the changes
        to allow the frontend an easier time to render the text.
        """
        text = text.replace("``", '"')
        text = text.replace("''", '"')
        return text

    def __init__(
        self, text, par_i=None, sent_i=None, token_i=None, has_space=None, pos=None,
        dep=None, head=None, lemma=None
    ):
        """
        sent_i - the sentence in the overall text.
        token_i - the index of the token in the original sentence.
        dep - dependency relation (e.g., 'compound:prt', 'nsubj', 'root')
        head - head token index (0-based, 0 = root)
        lemma - lemmatized form of the token
        """
        self.text = Token._token_punctuation_processing(text)
        self.is_sent_start = token_i == 0
        self.is_punct = Token.is_punctuation(self.text)
        self.is_symbol = Token.is_like_symbols(self.text)
        self.is_left_punct = text in Token.LEFT_PUNCTUATION
        self.is_right_punct = text in Token.RIGHT_PUNCTUATION
        self.par_i = par_i
        self.sent_i = sent_i
        self.token_i = token_i
        self.is_like_email = Token.is_like_email(text)
        self.is_like_url = Token.is_like_url(text)
        self.is_like_num = Token.NUM_REGEX.match(text) is not None
        self.has_space = has_space
        self.pos = pos
        self.dep = dep
        self.head = head
        self.lemma = lemma
        # MWE (Multi-Word Expression) fields - set by MWE detector after tokenization
        self.mwe_group_id = None
        self.mwe_role = None  # "head" | "dependent" | None
        self.mwe_type = None  # "particle_verb" | "grammatical" | "negation" | None
        self.mwe_partner_indices = []  # indices of partner tokens in the MWE
        self.mwe_is_separated = False  # True if MWE parts are not adjacent

    def __repr__(self):
        return self.text

    def as_serializable_dictionary(self):
        result = {
            "text": self.text,
            "is_sent_start": self.is_sent_start,
            "is_punct": self.is_punct,
            "is_symbol": self.is_symbol,
            "is_left_punct": self.is_left_punct,
            "is_right_punct": self.is_right_punct,
            "is_like_num": self.is_like_num,
            "sent_i": self.sent_i,
            "token_i": self.token_i,
            "paragraph_i": self.par_i,
            "is_like_email": self.is_like_email,
            "is_like_url": self.is_like_url,
            "has_space": self.has_space,
            "pos": self.pos,
            "dep": self.dep,
            "head": self.head,
            "lemma": self.lemma,
        }
        # Only include MWE fields if token is part of an MWE (to minimize payload)
        if self.mwe_group_id:
            result["mwe_group_id"] = self.mwe_group_id
            result["mwe_role"] = self.mwe_role
            result["mwe_type"] = self.mwe_type
            result["mwe_partner_indices"] = self.mwe_partner_indices
            result["mwe_is_separated"] = self.mwe_is_separated
        return result

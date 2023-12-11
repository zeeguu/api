import re
from nltk.stem.snowball import DutchStemmer, FrenchStemmer, DanishStemmer, GermanStemmer

LANGUAGE_STEMMER = {
    "da": DanishStemmer(),
    "de": GermanStemmer(),
    "fr": FrenchStemmer(),
    "nl": DutchStemmer()
}

def pre_process(s:str, language:str):
    s = s.lower()
    s = re.sub(r"(\d|[^A-Za-zÀ-ÖØ-öø-ÿ])+", " ", s)
    s = re.sub(r" {2,}", " ", s)
    stemmer = LANGUAGE_STEMMER.get(language, "")
    return " ".join([stemmer.stem(w) for w in s.split(" ")]).strip() if stemmer != "" else s
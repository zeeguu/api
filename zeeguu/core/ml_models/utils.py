import re
from nltk.stem import SnowballStemmer 
from zeeguu.core.model import Language

def remove_non_alphanumeric(s:str):
    s = s.lower()
    s = re.sub(r"(\d|[^A-Za-zÀ-ÖØ-öø-ÿ])+", " ", s)
    s = re.sub(r" {2,}", " ", s)
    return s.strip()

def stem_pre_process(s:str, language:str):
    s = remove_non_alphanumeric(s)
    lang_name = Language.LANGUAGE_NAMES[language].lower()
    if lang_name in SnowballStemmer.languages:
        stemmer = SnowballStemmer(lang_name)
        return " ".join([stemmer.stem(w) for w in s.split(" ")]).strip()
    return s



import os
from langdetect import detect
from .utils import stem_pre_process
from joblib import load

ml_models_path = os.path.dirname(__file__)
PAYWALL_TFIDF_MODEL = load(os.path.join(ml_models_path,'binary', 'tfidf_multi_paywall_detect.joblib'))

def is_paywalled(article_txt:str):
    lang = detect(article_txt)
    #print("Language detected was: ", lang)
    return PAYWALL_TFIDF_MODEL.predict([stem_pre_process(article_txt, lang)])[0]
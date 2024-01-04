
from langdetect import detect
from .utils import pre_process

def is_paywalled(article_txt:str, model):
    lang = detect(article_txt)
    #print("Language detected was: ", lang)
    return model.predict([pre_process(article_txt, lang)])
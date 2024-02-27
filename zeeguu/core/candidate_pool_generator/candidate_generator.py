from zeeguu.core.model import Language
from zeeguu.core.model import Article
from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from elasticsearch import Elasticsearch



def build_candidate_pool_for_lang(language: str, limit: int = None) -> list[Article]:
    '''Input must be in lowercase short form
    Examples: en, da, ru.. without limit you get about 30.000 articles returned here, its optional'''
    lang = Language.find(language)
    if(limit!=None):
        es = Elasticsearch(ES_CONN_STRING)
        es.search(index=ES_ZINDEX, body=query_body)
        pass
        #make limit 

    return Article.find_by_language(lang)
    
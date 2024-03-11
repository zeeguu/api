from zeeguu.core.content_retriever.parse_with_readability_server import (
    download_and_parse,
)

from zeeguu.api.app import create_app

from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from elasticsearch import Elasticsearch
from collections import Counter

from pprint import pprint

app = create_app()
app.app_context().push()

na = download_and_parse(
    "https://www.dr.dk/stories/1288510966/allerede-inden-oscar-showets-start-lurer-en-ny-skandale-i-kulissen"
)
print(na)

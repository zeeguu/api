import os


# Example of a elastic connection string: USERNAME:PASSWORD@127.0.0.1:9200
# if working without user and password, '127.0.0.1:9200' will suffice
ES_CONN_STRING = os.environ.get("ZEEGUU_ES_CONN_STRING", "http://127.0.0.1:9200")

# what index to use in elasticsearch
ES_ZINDEX = "zeeguu"

from codoc.service.graph import create_graph_of_module

import zeeguu_core

def bootstrap():
    return create_graph_of_module(zeeguu_core)

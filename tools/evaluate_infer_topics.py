from zeeguu.core.semantic_search import (
    semantic_search_from_article,
    semantic_search_add_topics_based_on_neigh,
    like_this_from_article,
)

from zeeguu.core.model.article import Article

from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from elasticsearch import Elasticsearch
from collections import Counter
import pandas as pd

from pprint import pprint
from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

es = Elasticsearch(ES_CONN_STRING)
# stats = es.indices.stats(index=ES_ZINDEX)
# pprint(stats)
IDS_TO_TEST = [
    # Danish Articles
    1063933,
    1063935,
    1063936,
    1063941,
    1063942,
    1063944,
    1063945,
    1064027,
    1064028,
    1064029,
    1064032,
    1064120,
    1064592,
    1065156,
    1065549,
    1065593,
    1065696,
    1067212,
    1068977,
    1074348,
    1077028,
    1080355,
    1083487,
    1084329,
    1085267,
    1085910,
    1087961,
    1090377,
    1095260,
    1096898,
    1097285,
    1104135,
    1125868,
    1126107,
    1128760,
    1128854,
    1129967,
    1130049,
    1130051,
    1130559,
    1131481,
    1131713,
    1132161,
    1132648,
    1133175,
    1133481,
    1133688,
    1135204,
    1137359,
    1138528,
    1147357,
    1147651,
    1157996,
    1158595,
    1181384,
    1193670,
    1193730,
    1210645,
    1218712,
    1220978,
    1224106,
    1224350,
    1224431,
    1225710,
    1234849,
    1237177,
    1237599,
    1237696,
    1250165,
    1252707,
    1255844,
    1257781,
    1260466,
    1262270,
    1262376,
    1267467,
    1275134,
    1283239,
    1283323,
    1289261,
    1296899,
    1297124,
    1301534,
    1304647,
    1306333,
    1306725,
    1313186,
    1315223,
    1315773,
    1326772,
    1330871,
    1344034,
    1344043,
    1345268,
    1354598,
    1355137,
    1360070,
    1360417,
    1361392,
    1363031,
    # English Articles
    883,
    892,
    13088,
    13088,
    14051,
    14210,
    14478,
    15495,
    15976,
    18194,
    24465,
    24800,
    25989,
    27904,
    31295,
    31295,
    34965,
    39292,
    39293,
    39716,
    39717,
    39728,
    49842,
    50526,
    50529,
    50829,
    51490,
    53472,
    53488,
    54068,
    54498,
    54780,
    54804,
    54951,
    54977,
    55122,
    55132,
    55134,
    55599,
    56583,
    56700,
    57272,
    57472,
    58121,
    58417,
    59364,
    59379,
    59711,
    61925,
    62709,
    63404,
    63458,
    64486,
    70018,
    70879,
    74936,
    78804,
    79030,
    92747,
    120770,
    154989,
    181409,
    181975,
    186598,
    187652,
    190425,
    203662,
    207767,
    207768,
    207771,
    207772,
    207901,
    207974,
    208067,
    208068,
    208100,
    208115,
    208173,
    208183,
    208218,
    208227,
    208229,
    208248,
    213072,
    216026,
    216360,
    216891,
    217031,
    217126,
    217334,
    217335,
    225128,
    226067,
    226171,
    226263,
    264641,
    269992,
    270336,
    286571,
    292165,
]

data_collected = []
# Done with 2491 articles.
# Using Danish Only
# Using k = 15, 85.71 % Predictions Acc,  6% Total Acc
# Using k = 5 , 78.37 % Predictions Acc, 29% Total Acc
# With English and Danish Data
# Using k = 15, 90.90 % Predictions Acc, 15  % Total Acc
# Using k = 5 , 81.44 % Predictions Acc, 39.5% Total Acc

for i in IDS_TO_TEST:
    doc_to_search = i
    article_to_search = Article.find_by_id(doc_to_search)
    k_to_use = 15
    a_found_t, hits_t = semantic_search_add_topics_based_on_neigh(
        article_to_search, k_to_use
    )

    neighbouring_topics = [t.new_topic for a in a_found_t for t in a.new_topics]
    neighbouring_keywords = [
        t.topic_keyword for a in a_found_t for t in a.topic_keywords
    ]

    topics_counter = Counter(neighbouring_topics)
    topics_key_counter = Counter(neighbouring_keywords)
    print("Topic Counts: ")
    pprint(topics_counter)
    print("Keyword Counts")
    pprint(topics_key_counter)
    print()
    og_topics = " ".join([str(t.new_topic.title) for t in article_to_search.new_topics])
    try:
        top_topic, count = topics_counter.most_common(1)[0]
        prediction = str(top_topic.title) if count >= ((k_to_use // 2) + 1) else ""
        print(f"Prediction: '{prediction}', Original: '{og_topics}'")
        data_collected.append(
            [
                i,
                article_to_search.title,
                og_topics,
                prediction,
                prediction in og_topics and prediction != "",
            ]
        )
    except Exception as e:
        data_collected.append([i, article_to_search.title, og_topics, "", False])

df = pd.DataFrame(
    data_collected, columns=["id", "title", "topic_url", "topic_inferred", "is_correct"]
)

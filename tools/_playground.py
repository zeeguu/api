import sys

from elasticsearch import Elasticsearch
from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from zeeguu.core.model import UserExerciseSession, User
import pandas as pd
from zeeguu.core.model import db
import matplotlib.pyplot as plt
import numpy as np
import pyarrow as pa # needed for pandas 

from zeeguu.api.app import create_app
from zeeguu.core.candidate_pool_generator.candidate_generator import build_candidate_pool_for_lang
from zeeguu.core.content_recommender.elastic_recommender import article_recommendations_for_user, article_search_for_user
from zeeguu.core.elastic.indexing import index_all_articles
from zeeguu.core.model import Language

app = create_app()
app.app_context().push()

'''
print("before the for")
for id in User.all_recent_user_ids(150):
    u = User.find_by_id(id)
    print(u.name)
    duration_old = exercises_duration_by_day(u)
    duration_new = exercises_duration_by_day(u)
    if duration_new != duration_old:
        print("old way")
        print(duration_old)
        print("new way")
        print(duration_new)


print("before test")
u = User.find_by_id(534)
print(u.name)
lan = u.learned_language
'''
'''
res = ElasticQuery(
    10,
    "cake",
    "sports, politics",
    "",
    "",
    "",
    lan,
    10,
    1
)
print (res)
'''

res = build_candidate_pool_for_lang("en")
print(len(res))

'''
#es2 = article_recommendations_for_user(u, 10)
term = "Ukraine"

res = article_search_for_user(u,20,term)
print(f"\nSearching for {term}\n")
for r in res: 
    print(r.topics)

print("\nSearching for standard recommendations\n The ones you see on the zeeguu main page\n")
res2 = article_recommendations_for_user(u,4)

for r in res2:
    print(r)

#print(res2)


conn = db.engine.raw_connection()

query = """
    SELECT * from user_reading_session urs
    LEFT JOIN article a ON urs.article_id = a.id
    WHERE urs.duration / a.word_count > 0.1
"""

query = """
    SELECT
        (urs.duration / 60 / 60) AS duration,
        a.word_count
    FROM
        user_reading_session urs
    LEFT JOIN
        article a ON urs.article_id = a.id
    JOIN
        (SELECT article_id, COUNT(*) AS session_count
        FROM user_reading_session
        GROUP BY article_id
        HAVING COUNT(*) >= 20) AS session_counts
    ON
        urs.article_id = session_counts.article_id
    WHERE
        urs.duration IS NOT NULL
        AND a.word_count IS NOT NULL
        AND urs.duration / 60 / 60 < 60
        AND urs.duration / 60 / 60 >= 2
        AND a.word_count < 2000
"""


upper_bound = True
lower_bound = True

y_start = 50

df = pd.read_sql_query(query, conn)
#df.to_csv(sys.stdout, index=False)
df.astype('int32').dtypes
df.plot(kind = 'scatter', x = 'duration', y = 'word_count', color='blue')

if upper_bound:
    x_values = df['duration']
    y_values_line = 20 * x_values + y_start
    plt.scatter(df['duration'], df['word_count'], label='Data Points')
    plt.plot(x_values, y_values_line, color='red', label='y = 2x + 2')

if lower_bound:
    x_values = df['duration']
    y_values_line = [y_start] * len(x_values)
    plt.scatter(df['duration'], df['word_count'], label='Data Points')
    plt.plot(x_values, y_values_line, color='red', label='y = 2x + 2')

plt.savefig('test.png')
print("Has been saved")
plt.show()


conn.close()




print("after test")



def initialize_all_focused_durations():
    for session in db['user_reading_session'].all():

        

def initialize_focused_duration(user_id, article_id):
    return
'''


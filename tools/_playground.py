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
from zeeguu.core.model.user_reading_session import UserReadingSession
from zeeguu.core.elastic.elastic_query_builder import ElasticQueryBuilder

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
'''

print("before test")

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

ElasticQueryBuilder.build_elastic_search_query(
    10,
    "search_terms",
    "topics",
    "unwanted_topics",
    "user_topics",
    "unwanted_user_topics",
    "language",
    100,
    10,
    "3d",
    0.8,
    4.2,
    False
)


conn.close()




print("after test")

'''
def initialize_all_focused_durations():
    for session in db['user_reading_session'].all():

        

def initialize_focused_duration(user_id, article_id):
    return
'''
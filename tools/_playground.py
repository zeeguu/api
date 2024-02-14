import sys
from zeeguu.core.model import UserExerciseSession, User
from zeeguu.core.user_statistics.activity import exercises_duration_by_day
import pandas as pd
from zeeguu.core.model import db

from zeeguu.api.app import create_app

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

query = "SELECT * from user limit 10"

df = pd.read_sql_query(query, conn)
df.to_csv(sys.stdout, index=False)

conn.close()
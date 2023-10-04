from zeeguu.core.model import UserExerciseSession, User
from zeeguu.api.app import create_app
from zeeguu.core.user_statistics.activity import exercises_duration_by_day

app = create_app()
app.app_context().push()

print("before the for")
for id in User.all_recent_user_ids(150):
    u = User.find_by_id(id)
    print(u.name)
    duration_old = exercises_duration_by_day(u)
    duration_new = exercises_duration_by_day(u, False)
    print(duration_old)
    print(duration_new)

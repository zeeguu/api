from zeeguu.core.model import UserExerciseSession, User
from zeeguu.api.app import create_app
from zeeguu.core.user_statistics.activity import exercises_duration_by_day

app = create_app()
app.app_context().push()

print("before the for")
for id in User.all_recent_user_ids(150):
    u = User.find_by_id(id)
    print(u.name)
    duration_old = exercises_duration_by_day(u, True)
    duration_new = exercises_duration_by_day(u)
    if duration_new != duration_old:
        print("old way")
        print(duration_old)
        print("new way")
        print(duration_new)

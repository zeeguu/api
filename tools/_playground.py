from zeeguu.core.model import User

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

print("before the for")
for id in User.all_recent_user_ids(10):
    u = User.find_by_id(id)
    print(u.name)

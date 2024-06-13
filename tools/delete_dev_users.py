import zeeguu.core
from zeeguu.core.model import User
from zeeguu.core.account_management.user_account_deletion import delete_user_account
from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session

# delete all anonymous users
for user in User.find_all():
    if "anon.zeeguu" in user.email:
        delete_user_account(db_session, user)

for user in User.query.filter_by(is_dev=True):
    print("deleting ... " + user.name)
    delete_user_account(db_session, user)

print("Remaining users: " + str(len(User.find_all())))

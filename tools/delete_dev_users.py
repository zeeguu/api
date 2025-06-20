import zeeguu.core
from zeeguu.core.model.user import User
from zeeguu.core.account_management.user_account_deletion import delete_user_account
from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session

# delete all anonymous users
anon_users = 0
for user in User.find_all():
    if "anon.zeeguu" in user.email:
        delete_user_account(db_session, user)
        anon_users += 1

dev_users = 0
for user in User.query.filter_by(is_dev=True):
    print("deleting ... " + user.name)
    delete_user_account(db_session, user)
    dev_users += 1

print("Deleted: anon=" + str(anon_users) + ", dev=" + str(dev_users))
print("Remaining users: " + str(len(User.find_all())))

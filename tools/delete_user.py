from zeeguu.api.app import create_app
import zeeguu.core
from zeeguu.core.account_management.user_account_deletion import delete_user_account

app = create_app()
app.app_context().push()
db_session = zeeguu.core.model.db.session

delete_user_account(
    db_session,
    "tfnribeiro@gmail.com",
    reason="Do not want to use Zeeguu anymore.",
    full_delete=True,
)
input("End... Any input to continue...")

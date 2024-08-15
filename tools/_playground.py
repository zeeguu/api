from zeeguu.core.content_retriever.parse_with_readability_server import (
    download_and_parse,
)
from zeeguu.core.model import User, UserActivityData
from zeeguu.core.util import find_last_reading_point

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

print("User: ", 4022)
user = User.find_by_id(4022)
last_sessions = UserActivityData.get_scroll_events_for_user_in_date_range(user, 90)
for s in last_sessions:
    print(s[2])
    print(find_last_reading_point(s[3]))
    print("##########################################")

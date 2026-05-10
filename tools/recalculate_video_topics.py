from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model.video import Video
import zeeguu

app = create_app_for_scripts()
app.app_context().push()

session = zeeguu.core.model.db.session
videos = Video.query.all()

for v in videos:
    v.assign_inferred_topics(session, False)
session.commit()

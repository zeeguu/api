from zeeguu.api.app import create_app
from zeeguu.core.elastic.basic_ops import (
    es_update,
    es_delete,
    es_get_es_id_from_video_id,
)
from zeeguu.core.model.video import Video
import zeeguu

app = create_app()
app.app_context().push()

session = zeeguu.core.model.db.session
videos = Video.query.filter_by(broken=1).all()

for v in videos:
    es_vid_id = es_get_es_id_from_video_id(v.id)
    es_delete(id=es_vid_id)

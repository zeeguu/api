import json
import os

from zeeguu.config import ZEEGUU_DATA_FOLDER
from zeeguu.core.model import db
from zeeguu.core.model.video import Video
from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

with open(
    os.path.join(ZEEGUU_DATA_FOLDER, "video", "video_unique_keys.json"), "r"
) as f:
    video_unique_keys = json.load(f)

for video_unique_key, lang in video_unique_keys.items():
    video = Video.find_or_create(db.session, video_unique_key, lang)
    print(video)

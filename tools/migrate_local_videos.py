import json
from zeeguu.core.model import db
from zeeguu.core.model.video import Video

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

with open("caption_table.json", "r") as f:
    caption_data = json.load(f)


video_unique_keys_and_language = {}

for caption in caption_data:
    video_unique_key = caption["video_unique_key"]
    language = caption["code"]

    if video_unique_key not in video_unique_keys_and_language:
        video_unique_keys_and_language[video_unique_key] = language

for video_unique_key, language in video_unique_keys_and_language.items():
    Video.find_or_create(db.session, video_unique_key, language)

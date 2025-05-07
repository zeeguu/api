from zeeguu.api.app import create_app
from zeeguu.core.model import db
from zeeguu.core.model.video import Video
from zeeguu.core.model.language import Language

from zeeguu.core.youtube_api.youtube_api import (
    is_video_language_correct,
    is_captions_too_short,
)

app = create_app()
app.app_context().push()

videos = Video.query.all()

print("removing videos with wrong language")
for video in videos:
    if video.broken == 0:
        video_language = video.language.code

        if not is_video_language_correct(
            video.title, video.description, video_language
        ):
            print(
                f"Video {video} has wrong language: {video_language}, setting to broken"
            )
            video.broken = 2

print("removing videos with too short captions")
for video in videos:
    if video.broken == 0:
        if is_captions_too_short(video.get_content(), video.duration):
            print(
                f"Video {video} has too short captions: {video_language}, setting to broken"
            )
            video.broken = 4

print("done")
db.session.commit()

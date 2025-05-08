from zeeguu.api.app import create_app
from zeeguu.core.model import db
from zeeguu.core.model.video import Video
from zeeguu.core.model.language import Language

from zeeguu.core.youtube_api.youtube_api import (
    is_video_language_correct,
    is_captions_too_short,
    NOT_IN_EXPECTED_LANGUAGE,
    CAPTIONS_TOO_SHORT,
)

app = create_app()
app.app_context().push()

videos = Video.query.all()

print("removing videos with wrong language")
for video in videos:
    if not video.broken:
        video_language = video.language.code

        if not is_video_language_correct(
            video.title, video.description, video_language
        ):
            print(
                f"Video {video} has wrong language: {video_language}, setting to broken"
            )
            video.broken = NOT_IN_EXPECTED_LANGUAGE

print("removing videos with too short captions")
for video in videos:
    if not video.broken:
        if is_captions_too_short(video.get_content(), video.duration):
            print(f"Video {video} has too short captions setting to broken")
            video.broken = CAPTIONS_TOO_SHORT

print("done")
db.session.commit()

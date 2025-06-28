"""
This script adds captions to videos that have broken status 1, if they exist in captions.json.

Use this script for videos that have already been crawled.

"""

from zeeguu.core.model.db import db
from zeeguu.core.model.video import Video
from zeeguu.core.model.caption import Caption
from zeeguu.api.app import create_app
from zeeguu.core.youtube_api.youtube_api import get_captions_from_json


app = create_app()
app.app_context().push()
db_session = db.session

# Get all videos with broken status 1
videos_with_broken_status_1 = Video.query.filter_by(broken=1).all()
print(f"Found {len(videos_with_broken_status_1)} videos with broken status 1")

# For each video with broken status 1, check if it has captions in captions.json
for video in videos_with_broken_status_1:
    captions = get_captions_from_json(video.video_unique_key)
    if captions:
        # Add captions from captions.json
        try:
            captions_list = captions["captions"]
            for caption in captions_list:
                new_caption = Caption.create(
                    session=db_session,
                    video=video,
                    time_start=caption["time_start"],
                    time_end=caption["time_end"],
                    text=caption["text"],
                )
                db_session.add(new_caption)
            # Save all captions for video
            print(
                f"Saving {len(captions_list)} captions for video {video.video_unique_key}..."
            )
            db_session.commit()

            # Set video broken status to 0 to indicate that the video is functional
            print(
                f"Setting video broken status to 0 for video {video.video_unique_key}..."
            )
            video.broken = 0  # SQLAlchemy detects this change on the managed object
            db_session.commit()
            print(
                f"SUCCESSFULLY ADDED CAPTIONS FOR VIDEO {video.video_unique_key} FROM captions.json."
            )
        except Exception as e:
            print(f"Error adding captions for video {video.video_unique_key}: {e}")
            db_session.rollback()
            raise e

    else:
        print(f"Video {video.video_unique_key} does not have captions in captions.json")

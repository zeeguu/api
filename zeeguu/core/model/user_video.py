from datetime import datetime

from sqlalchemy import or_
from zeeguu.core.model import db
from zeeguu.core.model.user import User
from zeeguu.core.model.video import Video
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model.video_caption_context import VideoCaptionContext
from zeeguu.core.util.encoding import datetime_to_json


class UserVideo(db.Model):
    __tablename__ = "user_video"
    table_args = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = db.relationship("User")
    video_id = db.Column(db.Integer, db.ForeignKey("video.id"))
    video = db.relationship("Video")

    db.UniqueConstraint("user_id", "video_id")

    opened = db.Column(db.DateTime)

    liked = db.Column(db.Boolean)

    playback_position = db.Column(db.Integer)

    def __init__(self, user, video, opened=None, liked=None, playback_position=None):
        self.user = user
        self.video = video
        self.opened = opened
        self.liked = liked
        self.playback_position = playback_position

    def __repr__(self):
        return (
            f"{self.user} and {self.video}: Opened: {self.opened}, Liked: {self.liked}"
        )

    def user_info_as_string(self):
        return f"{self.user} Opened: {self.opened}, Liked: {self.liked}"

    def set_opened(self, state=True):
        if state:
            self.opened = datetime.now()
        else:
            self.opened = None

    def set_liked(self, new_state=True):
        self.liked = new_state

    def last_intercation(self):
        if self.opened:
            return self.opened

    def set_playback_position(self, playback_position):
        self.playback_position = playback_position

    @classmethod
    def find_by_video(cls, video: Video):
        try:
            return cls.query.filter_by(video=video).all()
        except NoResultFound:
            return None

    @classmethod
    def find(cls, user: User, video: Video):
        try:
            return cls.query.filter_by(user=user, video=video).one()
        except NoResultFound:
            return None

    @classmethod
    def find_or_create(
        cls,
        session,
        user: User,
        video: Video,
        opened=None,
        liked=None,
        playback_position=None,
    ):
        try:
            return cls.query.filter_by(user=user, video=video).one()
        except NoResultFound:
            try:
                new = cls(
                    user,
                    video,
                    opened=opened,
                    liked=liked,
                    playback_position=playback_position,
                )
                session.add(new)
                session.commit()
                return new
            except Exception as e:
                from sentry_sdk import capture_exception

                capture_exception(e)
                print("Seems we avoided a race condition")
                session.rollback()
                return cls.query.filter_by(user=user, video=video).one()

    @classmethod
    def all_liked_videos_of_user(cls, user):
        return cls.query.filter_by(user=user).filter(UserVideo.liked.isnot(False).all())

    @classmethod
    def all_liked_videos_of_user_by_id(cls, user_id):
        return (
            cls.query.filter(UserVideo.user_id == user_id)
            .filter(UserVideo.liked == True)
            .all()
        )

    @classmethod
    def exists(cls, obj):
        try:
            cls.query.filter(cls.id == obj.id).one()
            return True
        except NoResultFound:
            return False

    @classmethod
    def user_video_info(
        cls, user: User, video: Video, with_content=False, with_translations=True
    ):
        from zeeguu.core.model import Bookmark
        from zeeguu.core.model.video_title_context import VideoTitleContext
        from zeeguu.core.model.user_activitiy_data import UserActivityData

        returned_info = video.video_info(with_content=with_content)
        user_video_info = UserVideo.find(user, video)
        # user_diff_feedback = VideoDifficultyFeedback.find(user, video)
        # user_topics_feedback = VideoTopicsFeedback.find_given_user_video(user, video)

        # if user_topics_feedback:
        #     video_topic_list = returned_info["topic_list"]
        #     topic_list = []
        #     topics_to_remove = set(
        #         [
        #             untf.topic.title
        #             for untf in user_topics_feedback
        #             if untf.feedback == VideoTopicUserFeedBack.DO_NOT_SHOW_FEEDBACK
        #         ]
        #     )
        #     for each in video_topic_list:
        #         title,_ = each
        #         if title not in topics_to_remove:
        #             topic_list.append(title)
        #     returned_info["topic_list"] = topic_list
        #     returned_info["topics"] = ",".join([t for t,_ in topic_list])

        if not user_video_info:
            returned_info["opened"] = False
            returned_info["liked"] = None
            returned_info["playback_position"] = None
            returned_info["translations"] = []

        else:
            returned_info["playback_position"] = user_video_info.playback_position
            returned_info["opened"] = user_video_info.opened is not None
            returned_info["liked"] = user_video_info.liked

            # if user_diff_feedback is not None:
            #     returned_info["relative_difficulty"] = (
            #         user_diff_feedback.difficulty_feedback
            #         )

            if with_translations:
                translations = Bookmark.find_all_for_user_and_source(user, video.source)
                returned_info["translations"] = [
                    each.as_dictionary() for each in translations
                ]

            if "captions" in returned_info:
                for caption in returned_info["captions"]:
                    caption["past_bookmarks"] = (
                        VideoCaptionContext.get_all_user_bookmarks_for_caption(
                            user.id, caption["context_identifier"]["video_caption_id"]
                        )
                    )

            if "tokenized_title" in returned_info:
                returned_info["tokenized_title"]["past_bookmarks"] = (
                    VideoTitleContext.get_all_user_bookmarks_for_video_title(
                        user.id, video.id
                    )
                )

        return returned_info

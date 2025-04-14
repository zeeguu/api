from datetime import datetime

from zeeguu.core.model import db
from zeeguu.core.model.caption import Caption
from zeeguu.core.model.language import Language
from zeeguu.core.model.url import Url
from zeeguu.core.model.video_tag import VideoTag
from zeeguu.core.model.video_tag_map import VideoTagMap
from zeeguu.core.model.video_topic_map import VideoTopicMap
from zeeguu.core.model.yt_channel import YTChannel
from zeeguu.core.model.source import Source
from zeeguu.core.model.source_type import SourceType
from zeeguu.core.model.bookmark_context import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.language.fk_to_cefr import fk_to_cefr
from zeeguu.core.util.encoding import datetime_to_json
from zeeguu.core.youtube_api.youtube_api import fetch_video_info, fetch_channel_info

MAX_CHAR_COUNT_IN_SUMMARY = 297

NO_CAPTIONS_AVAILABLE = 1
NOT_IN_EXPECTED_LANGUAGE = 2
DUBBED_AUDIO = 3


class Video(db.Model):
    __tablename__ = "video"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    video_unique_key = db.Column(db.String(512), unique=True, nullable=False)
    title = db.Column(db.String(512))
    description = db.Column(db.Text)
    published_time = db.Column(db.DateTime)
    channel_id = db.Column(db.Integer, db.ForeignKey("yt_channel.id"))
    thumbnail_url_id = db.Column(db.Integer, db.ForeignKey(Url.id))

    duration = db.Column(db.Integer)
    language_id = db.Column(db.Integer, db.ForeignKey("language.id"))
    vtt = db.Column(db.Text)

    source_id = db.Column(db.Integer, db.ForeignKey(Source.id), unique=True)
    source = db.relationship(Source, foreign_keys="Video.source_id")

    broken = db.Column(db.Integer)
    crawled_at = db.Column(db.DateTime)
    thumbnail_url = db.relationship(Url, foreign_keys="Video.thumbnail_url_id")

    channel = db.relationship("YTChannel", back_populates="videos")
    topics = db.relationship("VideoTopicMap", back_populates="video")
    language = db.relationship("Language")
    captions = db.relationship("Caption", back_populates="video")

    def __init__(
        self,
        video_unique_key,
        title,
        source,
        description,
        published_time,
        channel,
        thumbnail_url,
        duration,
        language,
        vtt,
        broken=0,
        crawled_at=datetime.now(),
    ):
        self.video_unique_key = video_unique_key
        self.title = title
        self.source = source
        self.description = description
        self.published_time = published_time
        self.channel = channel
        self.thumbnail_url = thumbnail_url
        self.duration = duration
        self.language = language
        self.vtt = vtt
        self.broken = broken
        self.crawled_at = crawled_at

    def __repr__(self):
        return f"<Video title: {self.title} unique_key: {self.video_unique_key}>"

    def get_content(self):
        return self.source.get_content()

    @classmethod
    def find_by_id(cls, video_id: int):
        return cls.query.filter_by(id=video_id).first()

    @classmethod
    def find_or_create(
        cls,
        session,
        video_unique_key,
        language,
        upload_index=True,
    ):
        from zeeguu.core.elastic.indexing import index_video

        video = (
            session.query(cls).filter(cls.video_unique_key == video_unique_key).first()
        )

        if video:
            print(f"Video already crawled. Returning... (Broken: {video.broken})")
            return video

        try:
            video_info = fetch_video_info(video_unique_key, language)
        except ValueError as e:
            print(f"Error fetching video info for {video_unique_key}: {e}")
            return None

        if isinstance(language, str):
            language = session.query(Language).filter_by(code=language).first()

        channel_info = fetch_channel_info(video_info["channelId"])

        thumbnail_url = channel_info["thumbnail"]
        channel = YTChannel.find_or_create(
            session, video_info["channelId"], channel_info, thumbnail_url, language
        )

        # TODO: Remove this right? This prevents us from saving videos with no text (e.g. )
        # if video_info["text"] == "":
        #     print(f"Couldn't parse any text for the video '{video_unique_key}'")
        #     return None

        url_object = Url.find_or_create(session, video_info["thumbnail"])

        # TODO: Remove this temporary workaround (this is because source_id is unique in video table)
        if video_info["broken"] != 0:
            source = None
        else:
            source = Source.find_or_create(
                session,
                video_info["text"],
                SourceType.find_by_type(SourceType.VIDEO),
                language,
                False,
                False,
            )

        new_video = cls(
            video_unique_key=video_unique_key,
            title=video_info["title"],
            source=source,
            description=video_info["description"],
            published_time=video_info["publishedAt"],
            channel=channel,
            thumbnail_url=url_object,
            duration=video_info["duration"],
            language=language,
            vtt=video_info["vtt"],
            broken=video_info["broken"],
        )
        session.add(new_video)

        try:
            session.commit()
        except Exception as e:
            session.rollback()
            raise e

        # Skip captions and topic if video is broken (this also means that the video is not indexed)
        if video_info["broken"] != 0:
            return new_video

        # Add captions
        try:
            for caption in video_info["captions"]:
                new_caption = Caption.create(
                    session=session,
                    video=new_video,
                    time_start=caption["time_start"],
                    time_end=caption["time_end"],
                    text=caption["text"],
                )
                session.add(new_caption)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e

        try:
            for tag_text in video_info["tags"]:
                new_tag = VideoTag.find_or_create(session, tag_text)
                video_tag_map = VideoTagMap.find_or_create(
                    session, video=new_video, tag=new_tag
                )
            session.commit()
        except Exception as e:
            session.rollback()
            raise e

        # add topic
        print("Adding topic")
        try:
            # new_video.assign_inferred_topics(session)
            print("Pretend topic")
        except Exception as e:
            print(
                f"Error adding topic to video ({video_unique_key}) with elastic search: {e}"
            )
            print("Video will be saved without a topic for now.")
            session.rollback()

        # Index video if it is not broken
        if new_video.broken == 0:
            index_video(new_video, session)

        return new_video

    def assign_inferred_topics(self, session, commit=True):
        from zeeguu.core.model.article_topic_map import TopicOriginType
        from zeeguu.core.semantic_search import (
            get_topic_classification_based_on_similar_content,
        )

        topic = get_topic_classification_based_on_similar_content(
            self.get_content(), verbose=True
        )
        if topic:
            video_topic_map = VideoTopicMap(
                video=self, topic=topic, origin_type=TopicOriginType.INFERRED
            )
            print(f"Assigned Topic: {video_topic_map}")
            session.add(video_topic_map)
            if commit:
                session.commit()
        else:
            print(
                f"No topic generated for video ({self.video_unique_key}) using elastic search."
            )

    def topics_as_tuple(self):
        topics = []
        for topic in self.topics:
            if topic.topic.title == "" or topic.topic.title is None:
                continue
            topics.append((topic.topic.title, topic.origin_type))
        return topics

    def video_info(self, with_content=False):
        text = self.get_content()
        summary = text[:MAX_CHAR_COUNT_IN_SUMMARY].replace("\n", " ") + "..."
        result_dict = dict(
            id=self.id,
            video_unique_key=self.video_unique_key,
            source_id=self.source.id,
            title=self.title,
            description=self.description,
            summary=summary,
            channel=self.channel.as_dictionary(),
            thumbnail_url=(
                self.thumbnail_url.as_string() if self.thumbnail_url else None
            ),
            topics_list=self.topics_as_tuple(),
            duration=self.duration,
            language_code=self.language.code,
            metrics=dict(
                difficulty=self.source.fk_difficulty / 100,
                cefr_level=fk_to_cefr(self.source.fk_difficulty),
            ),
            video=True,
        )

        if self.published_time:
            result_dict["published_time"] = datetime_to_json(self.published_time)

        if with_content:
            from zeeguu.core.tokenization import get_tokenizer, TOKENIZER_MODEL

            tokenizer = get_tokenizer(self.language, TOKENIZER_MODEL)
            result_dict["captions"] = [
                {
                    "time_start": caption.time_start / 1000,  # convert to seconds
                    "time_end": caption.time_end / 1000,
                    "text": caption.get_content(),
                    "tokenized_text": tokenizer.tokenize_text(
                        caption.get_content(), flatten=False
                    ),
                    "context_identifier": ContextIdentifier(
                        ContextType.VIDEO_CAPTION, video_caption_id=caption.id
                    ).as_dictionary(),
                }
                for caption in self.captions
            ]

            result_dict["tokenized_title"] = {
                "tokens": tokenizer.tokenize_text(self.title, flatten=False),
                "context_identifier": ContextIdentifier(
                    ContextType.VIDEO_TITLE, video_id=self.id
                ).as_dictionary(),
            }

        return result_dict

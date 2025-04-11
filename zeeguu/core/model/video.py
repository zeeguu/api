from datetime import datetime
import html
from io import StringIO
import os
import re
import isodate
import requests
import webvtt
import yt_dlp
import emoji

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

from langdetect import detect
from zeeguu.core.model.bookmark_context import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.util.fk_to_cefr import fk_to_cefr
from zeeguu.core.util.encoding import datetime_to_json
from dotenv import load_dotenv
from zeeguu.core.util.text import remove_emojis

load_dotenv()

API_FOR_LANGUAGE = {
    "da": os.getenv("YOUTUBE_API_KEY_DA"),
    "es": os.getenv("YOUTUBE_API_KEY_ES"),
}

MAX_CHAR_COUNT_IN_SUMMARY = 297

SOCIAL_MEDIA_WORDS = [
    "instagram",
    "facebook",
    "twitter",
    "snapchat",
    "tiktok",
    "pinterest",
    "linkedin",
    "youtube",
    "whatsapp",
    "reddit",
    "tumblr",
    "twitch",
    "x.com",
    "discord",
    "threads",
]

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
    published_at = db.Column(db.DateTime)
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
        published_at,
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
        self.published_at = published_at
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
            video_info = cls.fetch_video_info(video_unique_key, language)
        except ValueError as e:
            print(f"Error fetching video info for {video_unique_key}: {e}")
            return None

        if isinstance(language, str):
            language = session.query(Language).filter_by(code=language).first()

        title_lang = detect(video_info["title"]) if video_info["title"] else None
        desc_lang = (
            detect(clean_description(video_info["description"]))
            if video_info["description"]
            else None
        )
        print(
            f"Video detect languages detected are (title: '{title_lang}', description: '{desc_lang}')."
        )
        if (title_lang and title_lang != language.code) and (
            desc_lang and desc_lang != language.code
        ):
            print(
                f"Video title and description ({video_unique_key}) is not in language: {language.code}"
            )
            video_info["broken"] = NOT_IN_EXPECTED_LANGUAGE

        if has_dubbed_audio(video_unique_key):
            print(f"Video ({video_unique_key}) has dubbed audio")
            video_info["broken"] = DUBBED_AUDIO

        channel = YTChannel.find_or_create(session, video_info["channelId"], language)

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
            published_at=video_info["publishedAt"],
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

        # Skip captions and topic if video is broken
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
            new_video.assign_inferred_topics(session)
        except Exception as e:
            print(
                f"Error adding topic to video ({video_unique_key}) with elastic search: {e}"
            )
            print("Video will be saved without a topic for now.")
            session.rollback()
        if video.broken == 0:
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

    @staticmethod
    def fetch_video_info(video_unique_key, lang):
        """
        video_unique_key is the video id, e.g. "8-GrLwHK8SQ"


        """

        def _get_thumbnail(item):
            return (
                item["snippet"]["thumbnails"].get("maxres", {}).get("url")
                or item["snippet"]["thumbnails"].get("high", {}).get("url")
                or item["snippet"]["thumbnails"].get("medium", {}).get("url")
                or item["snippet"]["thumbnails"]
                .get("default", {})
                .get("url", "No thumbnail available")
            )

        VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
        YOUTUBE_API_KEY = API_FOR_LANGUAGE.get(lang)

        if not YOUTUBE_API_KEY:
            raise ValueError("Missing YOUTUBE_API_KEY environment variable. ")
        params = {
            "part": "snippet,contentDetails",
            "id": video_unique_key,
            "key": YOUTUBE_API_KEY,
        }

        response = requests.get(VIDEO_URL, params=params)
        video_data = response.json()

        if "items" not in video_data or not video_data["items"]:
            raise ValueError(
                f"Video {video_unique_key} not found, or API quota exceeded"
            )

        item = video_data["items"][0]

        video_info = {
            "videoId": video_unique_key,
            "title": remove_emojis(item["snippet"]["title"]),
            "description": remove_emojis(item["snippet"].get("description", "")),
            "publishedAt": isodate.parse_datetime(
                item["snippet"]["publishedAt"]
            ).replace(tzinfo=None),
            "channelId": item["snippet"]["channelId"],
            "thumbnail": _get_thumbnail(item),
            "tags": item["snippet"].get("tags", []),
            "duration": int(
                isodate.parse_duration(
                    item["contentDetails"]["duration"]
                ).total_seconds()
            ),
        }

        captions = Video.get_captions(video_unique_key, lang)
        if captions is None:
            print(f"Could not fetch captions for video {video_unique_key} in {lang}")
            video_info["vtt"] = ""
            video_info["text"] = ""
            video_info["captions"] = []
            video_info["broken"] = NO_CAPTIONS_AVAILABLE
        else:
            video_info["vtt"] = captions["vtt"]
            video_info["text"] = captions["text"]
            video_info["captions"] = captions["captions"]
            video_info["broken"] = 0

        return video_info

    @staticmethod
    def get_captions(video_unique_key, lang):
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "writesubtitles": True,
            "subtitleslangs": [lang],
            "subtitlesformat": "vtt",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_unique_key}",
                    download=False,
                )
                subtitles = info.get("subtitles", {})

                if lang in subtitles:
                    url = subtitles[lang][-1]["url"]

                    response = requests.get(url)
                    if response.status_code == 200:
                        vtt_content = clean_vtt(response.text)
                        return Video.parse_vtt(vtt_content)
                return None
            except Exception as e:
                print(f"Error fetching subtitles for {video_unique_key}: {e}")
                return None

    @staticmethod
    def parse_vtt(vtt_content):
        def _timestamp_to_milliseconds(timestamp):
            h, m, s = timestamp.replace(",", ".").split(":")
            return (float(h) * 3600 + float(m) * 60 + float(s)) * 1000

        captions_list = []
        full_text = []

        vtt_file = StringIO(vtt_content)
        captions = webvtt.read_buffer(vtt_file)

        for caption in captions:
            captions_list.append(
                {
                    "time_start": _timestamp_to_milliseconds(caption.start),
                    "time_end": _timestamp_to_milliseconds(caption.end),
                    "text": caption.text,
                }
            )
            full_text.append(caption.text)

        return {
            "vtt": vtt_content,
            "text": "\n".join(full_text),
            "captions": captions_list,
        }

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

        if self.published_at:
            result_dict["published_at"] = datetime_to_json(self.published_at)

        if with_content:
            from zeeguu.core.tokenization import get_tokenizer, TOKENIZER_MODEL

            tokenizer = get_tokenizer(self.language, TOKENIZER_MODEL)
            result_dict["captions"] = [
                {
                    "time_start": caption.time_start / 1000, # convert to seconds
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
                "tokenized_title": tokenizer.tokenize_text(self.title, flatten=False),
                "context_identifier": ContextIdentifier(
                    ContextType.VIDEO_TITLE, video_id=self.id
                ).as_dictionary(),
            }

        return result_dict


def clean_description(description_text):
    # remove hashtags
    description_text = re.sub(r"#\w+", "", description_text)

    # remove @mentions
    description_text = re.sub(r"@\w+", "", description_text)

    # remove social media words
    for word in SOCIAL_MEDIA_WORDS:
        description_text = re.sub(
            rf"\b{word}\b", "", description_text, flags=re.IGNORECASE
        )

    # collapse multiple spaces and trim
    description_text = re.sub(r"\s+", " ", description_text).strip()

    return description_text


def has_dubbed_audio(video_unique_key):
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "force_generic_extractor": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_unique_key}",
                download=False,
            )

            for format in info.get("formats", []):
                if "dubbed-auto" in format.get("format_note", "").lower():
                    return True
            return False

    except Exception as e:
        print(f"Error checking for dubbed audio: {e}")
        return False


def clean_vtt(vtt_content):
    vtt_content = html.unescape(vtt_content)
    vtt_content = remove_emojis(vtt_content)
    return vtt_content

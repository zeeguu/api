from io import StringIO
import os
import isodate
import requests
import webvtt
import yt_dlp
from zeeguu.core.language.difficulty_estimator_factory import DifficultyEstimatorFactory
from zeeguu.core.model import db
from zeeguu.core.model.caption import Caption
from zeeguu.core.model.language import Language
from zeeguu.core.model.topic import Topic
from zeeguu.core.model.video_tag import VideoTag
from zeeguu.core.model.video_tag_map import VideoTagMap
from zeeguu.core.model.video_topic_map import VideoTopicMap
from zeeguu.core.model.yt_channel import YTChannel
from langdetect import detect
# from tools.run_knn_classification_with_text import get_topic_classification_based_on_similar_content

from zeeguu.core.util.encoding import datetime_to_json

from dotenv import load_dotenv
load_dotenv()

languages = {
    "da": os.getenv("YOUTUBE_API_KEY_DA"),
    "es": os.getenv("YOUTUBE_API_KEY_ES"),
}

MAX_CHAR_COUNT_IN_SUMMARY = 300

class Video(db.Model):
    __tablename__ = 'video'
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.String(512), unique=True, nullable=False)
    title = db.Column(db.String(512))
    description = db.Column(db.Text)
    published_at = db.Column(db.DateTime)
    channel_id = db.Column(db.Integer, db.ForeignKey("yt_channel.id"))
    thumbnail_url = db.Column(db.String(512))
    duration = db.Column(db.Integer)
    language_id = db.Column(db.Integer, db.ForeignKey("language.id"))
    vtt = db.Column(db.Text)
    plain_text = db.Column(db.Text)
    fk_difficulty = db.Column(db.Integer)

    channel = db.relationship("YTChannel", back_populates="videos")
    language = db.relationship("Language")
    captions = db.relationship("Caption", back_populates="video")

    def __init__(self, video_id, title, description, published_at, channel, thumbnail_url, duration, language, vtt, plain_text):
        self.video_id = video_id
        self.title = title
        self.description = description
        self.published_at = published_at
        self.channel = channel
        self.thumbnail_url = thumbnail_url
        self.duration = duration
        self.language = language
        self.vtt = vtt
        self.plain_text = plain_text
        self.compute_fk_difficulty()

    def __repr__(self):
        return f'<Video {self.title} ({self.video_id})>'

    def as_dictionary(self):
        return dict(
            id=self.id,
            video_id=self.video_id,
            title=self.title,
            description=self.description,
            published_at=self.published_at,
            channel=self.channel.as_dictionary(),
            thumbnail_url=self.thumbnail_url,
            duration=self.duration,
            language_id=self.language.id,
            vtt=self.vtt,
            plain_text=self.plain_text
        )

    def compute_fk_difficulty(self):
        fk_estimator = DifficultyEstimatorFactory.get_difficulty_estimator("fk")
        fk_difficulty = fk_estimator.estimate_difficulty(
            self.plain_text, self.language, None
            )
        self.fk_difficulty = fk_difficulty["grade"]

    @classmethod
    def find_or_create(
        cls, 
        session, 
        video_id,
        language, 
    ):
        video = session.query(cls).filter_by(video_id=video_id).first()

        if video:
            return video
        
        try:
            video_info = cls.fetch_video_info(video_id, language)
        except ValueError as e:
            print(f"Error fetching video info for {video_id}: {e}")
            return None

        if video_info is None:
            return None

        if isinstance(language, str):
            language = session.query(Language).filter_by(code=language).first()
        
        title_lang = detect(video_info["title"]) if video_info["title"] else None
        desc_lang = detect(video_info["description"]) if video_info["description"] else None

        if title_lang and title_lang != language.code and desc_lang and desc_lang != language.code:
            print(f"Video {video_id} is not in {language.code}")
            return None

        channel = YTChannel.find_or_create(session, video_info["channelId"], language)
        
        new_video = cls(
            video_id = video_id,
            title = video_info["title"],
            description = video_info["description"],
            published_at = video_info["publishedAt"],
            channel = channel,
            thumbnail_url = video_info["thumbnail"],
            duration = video_info["duration"],
            language = language,
            vtt = video_info["vtt"],
            plain_text = video_info["text"]
        )
        session.add(new_video)

        try:
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        

        try:
            for caption in video_info["captions"]:
                new_caption = Caption(
                    video=new_video,
                    time_start=caption["time_start"],
                    time_end=caption["time_end"],
                    text=caption["text"]
                )
                session.add(new_caption)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        
        try:
            for tag_text in video_info["tags"]:
                new_tag = VideoTag.find_or_create(session, tag_text)
                video_tag_map = VideoTagMap(
                    video=new_video,
                    tag=new_tag
                )
                session.add(new_tag)
                session.add(video_tag_map)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e


        # add topic
        print("Adding topic")
        try:
            #topic_title = get_topic_classification_based_on_similar_content(new_video.plain_text)
            topic_title = "Technology & Science"
            print(f"Topic title: {topic_title}")
            if topic_title:
                topic = session.query(Topic).filter_by(title=topic_title).first()
                print(f"Topic: {topic}")
                video_topic_map = VideoTopicMap(
                    video=new_video,
                    topic=topic
                )
                print(f"Video topic map: {video_topic_map}")
                session.add(video_topic_map)
                session.commit()
        except Exception as e:
            session.rollback()
            raise e

        return new_video
    
    @staticmethod
    def fetch_video_info(videoId, lang):
        VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
        YOUTUBE_API_KEY = languages.get(lang)

        if not YOUTUBE_API_KEY:
            raise ValueError("Missing YOUTUBE_API_KEY environment variable")
        params = {
            "part": "snippet,contentDetails",
            "id": videoId,
            "key": YOUTUBE_API_KEY,
        }

        response = requests.get(VIDEO_URL, params=params)
        video_data = response.json()

        if "items" not in video_data or not video_data["items"]:
            raise ValueError(f"Video {videoId} not found, or API quota exceeded")
        
        captions = Video.get_captions(videoId, lang)
        if captions is None:
            print(f"Could not fetch captions for video {videoId} in {lang}")
            return None
        
        item = video_data["items"][0]

        video_info = {
            "videoId": videoId,
            "title": item["snippet"]["title"],
            "description": item["snippet"].get("description", ""),
            "publishedAt": isodate.parse_datetime(item["snippet"]["publishedAt"]).replace(tzinfo=None),
            "channelId": item["snippet"]["channelId"],
            "thumbnail": item["snippet"]["thumbnails"].get("maxres", {}).get("url", "No maxres thumbnail available"),
            "tags": item["snippet"].get("tags", []),
            "duration": int(isodate.parse_duration(item["contentDetails"]["duration"]).total_seconds()),
            "vtt": captions["vtt"],
            "text": captions["text"],
            "captions": captions["captions"]
        }

        return video_info

    @staticmethod
    def get_captions(video_id, lang):
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "writesubtitles": True,
            "subtitleslangs": [lang],
            "subtitlesformat": "vtt",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                subtitles = info.get("subtitles", {})

                if lang in subtitles:
                    url = subtitles[lang][-1]["url"]

                    response = requests.get(url)
                    if response.status_code == 200:
                        vtt_content = response.text
                        return Video.parse_vtt(vtt_content)
                return None
            except Exception as e:
                print(f"Error fetching subtitles for {video_id}: {e}")
                return None

    @staticmethod
    def parse_vtt(vtt_content):
        captions_list = []
        full_text = []

        vtt_file = StringIO(vtt_content)
        captions = webvtt.read_buffer(vtt_file)

        for caption in captions:
            captions_list.append({
                "time_start": caption.start_in_seconds,
                "time_end": caption.end_in_seconds,
                "text": caption.text,
            })
            full_text.append(caption.text)
        
        return {
            "vtt": vtt_content,
            "text": "\n".join(full_text),
            "captions": captions_list
        }
    
    def video_info(self):
        def fk_to_cefr(fk_difficulty):
            if fk_difficulty < 17:
                return "A1"
            elif fk_difficulty < 34:
                return "A2"
            elif fk_difficulty < 51:
                return "B1"
            elif fk_difficulty < 68:
                return "B2"
            elif fk_difficulty < 85:
                return "C1"
            else:
                return "C2"
            
        summary = self.plain_text[:MAX_CHAR_COUNT_IN_SUMMARY]
        result_dict = dict(
            id=self.id,
            video_id=self.video_id,
            title=self.title,
            description=self.description,
            summary=summary,
            channel=self.channel.as_dictionary(),
            thumbnail_url=self.thumbnail_url,
            duration=self.duration,
            language_code=self.language.code,
            vtt=self.vtt,
            plain_text=self.plain_text,
            metrics=dict(
                difficulty=self.fk_difficulty / 100,
                cefr_level=fk_to_cefr(self.fk_difficulty),
            )
        )

        if self.thumbnail_url:
            result_dict["thumbnail_url"] = self.thumbnail_url

        if self.published_at:
            result_dict["published_at"] = datetime_to_json(self.published_at)
        
        from zeeguu.core.tokenization import get_tokenizer, TOKENIZER_MODEL

        tokenizer = get_tokenizer(self.language, TOKENIZER_MODEL)
        result_dict["captions"] = [
            {
                "time_start": caption.time_start,
                "time_end": caption.time_end,
                "text": caption.text,
                "tokenized_text": tokenizer.tokenize_text(caption.text, flatten=False),
            }
            for caption in self.captions
        ]

        result_dict["tokenized_title"] = tokenizer.tokenize_text(self.title, flatten=False)
        
        return result_dict
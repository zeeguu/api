import html
import json
import os
import re
import isodate
import requests

from zeeguu.config import ZEEGUU_DATA_FOLDER
from zeeguu.core.util.text import remove_emojis
from langdetect import detect, LangDetectException
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    CouldNotRetrieveTranscript,
)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
if not YOUTUBE_API_KEY:
    print("No YOUTUBE_API_KEY found in environment variables.")

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
    "subscribe",
    "follow",
    "like",
    "share",
    "comment",
]


NO_CAPTIONS_AVAILABLE = 1
NOT_IN_EXPECTED_LANGUAGE = 2
DUBBED_AUDIO = 3
CAPTIONS_TOO_SHORT = 4
VIDEO_IS_MISSING_DURATION = 5

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def get_video_unique_keys(lang, category_id=None, topic_id=None, max_results=50):
    """
    This provides a list of video ids (no video information is provided).

    The actual data extraction is done at fetch_video_info
    """
    if max_results > 50:
        print(
            f"max_results was higher than 50 ({max_results}), Youtube only allows a max of 50..."
        )

    # see https://developers.google.com/youtube/v3/docs/search/list
    # Quota: 100 units per call. Up to 50 videos per call

    search_params = {
        "part": "id",
        "videoCategoryId": category_id,
        "topicId": topic_id,
        "type": "video",
        "videoCaption": "closedCaption",
        "videoEmbeddable": "true",
        "relevanceLanguage": lang,
        "videoDuration": "medium",
        "maxResults": max_results,  # Max results is 50 (can be lower)
        "key": YOUTUBE_API_KEY,
    }

    response = requests.get(SEARCH_URL, params=search_params)
    search_data = response.json()

    video_ids = [item["id"]["videoId"] for item in search_data.get("items", [])]
    if not video_ids:
        return []

    return video_ids


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
    # see https://developers.google.com/youtube/v3/docs/videos/list
    # Quota: 1 unit per video

    params = {
        "part": "snippet,contentDetails",
        "id": video_unique_key,
        "key": YOUTUBE_API_KEY,
    }

    response = requests.get(VIDEO_URL, params=params)
    video_data = response.json()

    if "items" not in video_data or not video_data["items"]:
        raise ValueError(f"Video {video_unique_key} not found, or API quota exceeded")

    item = video_data["items"][0]

    video_info = {
        "video_unique_key": video_unique_key,
        "title": remove_emojis(item["snippet"]["title"]),
        "description": remove_emojis(item["snippet"].get("description", "")),
        "publishedAt": isodate.parse_datetime(item["snippet"]["publishedAt"]).replace(
            tzinfo=None
        ),
        "channelId": item["snippet"]["channelId"],
        "thumbnail": _get_thumbnail(item),
        "tags": item["snippet"].get("tags", []),
        "text": "",
        "captions": [],
        "broken": 0,
    }

    # Check video duration: some videos don't have a duration because they are not released yet or are special videos like shorts.
    try:
        video_info["duration"] = int(
            isodate.parse_duration(item["contentDetails"]["duration"]).total_seconds()
        )
    except KeyError:
        print(
            f"Duration not found for video {video_unique_key}. Setting video to broken and its duration to 0."
        )
        video_info["duration"] = 0
        video_info["broken"] = VIDEO_IS_MISSING_DURATION
        return video_info

    if not is_video_language_correct(
        video_info["title"], video_info["description"], lang
    ):
        print(f"Video {video_unique_key} is not in the expected language {lang}.")
        video_info["broken"] = NOT_IN_EXPECTED_LANGUAGE
        return video_info

    captions = get_captions_from_json(video_unique_key, lang)
    if captions is None:
        print(f"Could not fetch captions for video {video_unique_key} in {lang}")
        video_info["broken"] = NO_CAPTIONS_AVAILABLE
    elif is_captions_too_short(captions["text"], video_info["duration"]):
        video_info["broken"] = CAPTIONS_TOO_SHORT
    else:
        video_info["text"] = captions["text"]
        video_info["captions"] = captions["captions"]

    return video_info


def get_captions_with_yttapi(video_unique_key, lang):
    try:
        print(f"Fetching captions via Python Package: youtube_transcript_api...")
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_unique_key)
        transcript = transcript_list.find_manually_created_transcript([lang])

        transcript_data = transcript.fetch()
        transcript_data = transcript.fetch()

        caption_list = []
        full_text = []
        caption_list = []
        full_text = []

        for caption in transcript_data:
            clean_text = text_cleaner(caption.text)
            caption_list.append(
                {
                    "time_start": caption.start * 1000,
                    "time_end": (caption.start + caption.duration) * 1000,
                    "text": clean_text,
                }
            )
            full_text.append(clean_text)
        for caption in transcript_data:
            clean_text = text_cleaner(caption.text)
            caption_list.append(
                {
                    "time_start": caption.start * 1000,
                    "time_end": (caption.start + caption.duration) * 1000,
                    "text": clean_text,
                }
            )
            full_text.append(clean_text)

        return {
            "text": "\n".join(full_text),
            "captions": caption_list,
        }

    except TranscriptsDisabled:
        print("Transcript is disabled for this video.")
        return None
    except NoTranscriptFound:
        print(
            "No manually added transcript was found for this video in the specified language."
        )
        return None
    except VideoUnavailable:
        print("Video is unavailable.")
        return None
    except CouldNotRetrieveTranscript as e:
        print(f"Could not retrieve transcript: {e}")
        return None
    except Exception as e:
        print(f"Error fetching captions for {video_unique_key}: {e}")
        return None


def get_captions_from_json(video_unique_key, lang):
    """
    Temporary solution to fetch captions from uploaded file with captions (captions.json)
    """
    try:
        print("Fetching captions from captions.json...")
        captions_path = os.path.join(ZEEGUU_DATA_FOLDER, "video", "captions.json")
        print(f"Looking for captions file at: {captions_path}")

        with open(captions_path, "r", encoding="utf-8") as f:
            caption_data = json.load(f)
        print(f"Found {len(caption_data)} captions in captions.json")

        caption_list = []
        full_text = []

        print(f"Searching for video {video_unique_key} in captions.json...")
        for caption in caption_data:
            if caption["video_unique_key"] == video_unique_key:

                caption_list.append(
                    {
                        "time_start": caption["time_start"],
                        "time_end": caption["time_end"],
                        "text": caption["text"],
                    }
                )
                full_text.append(caption["text"])

        print(
            f"FOUND {len(caption_list)} CAPTIONS FOR VIDEO {video_unique_key} IN captions.json"
        )

        if len(caption_list) == 0:
            return None
        else:
            return {
                "text": "\n".join(full_text),
                "captions": caption_list,
            }
    except FileNotFoundError:
        print(f"Caption file not found at {captions_path}.")
        return None


def text_cleaner(text):
    text = html.unescape(text)
    text = remove_emojis(text)
    return text


def is_video_language_correct(title, description, language):
    def _clean_description(description_text):
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

    try:
        title_lang = detect(title) if title else None
    except LangDetectException:
        title_lang = None

    try:
        cleaned_description = _clean_description(description) if description else ""
        desc_lang = detect(cleaned_description) if cleaned_description else None
    except LangDetectException:
        desc_lang = None

    if (title_lang and title_lang == language) or (desc_lang and desc_lang == language):
        return True
    return False


def fetch_channel_info(channel_id):
    def _get_thumbnail(snippet):
        return (
            snippet["thumbnails"].get("high", {}).get("url")
            or snippet["thumbnails"].get("medium", {}).get("url")
            or snippet["thumbnails"]
            .get("default", {})
            .get("url", "No thumbnail available")
        )

    CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"
    # see https://developers.google.com/youtube/v3/docs/channels/list
    # Quota: 1 unit per channel

    channel_params = {
        "part": "snippet,statistics",
        "id": channel_id,
        "key": YOUTUBE_API_KEY,
    }

    response = requests.get(CHANNEL_URL, params=channel_params)
    channel_data = response.json()

    channel = channel_data.get("items", [])[0]
    snippet = channel["snippet"]
    statistics = channel["statistics"]

    channel_info = {
        "channelId": channel_id,
        "channelName": remove_emojis(snippet["title"]),
        "description": remove_emojis(snippet.get("description", "")),
        "viewCount": statistics["viewCount"],
        "subscriberCount": statistics["subscriberCount"],
        "thumbnail": _get_thumbnail(snippet),
    }

    return channel_info


def is_captions_too_short(caption_text: str, video_duration_in_seconds: int) -> bool:
    # After consolidating different videos and captions, we have found that 1 word per second is a good threshold
    if len(caption_text.split()) < video_duration_in_seconds:
        return True
    else:
        return False

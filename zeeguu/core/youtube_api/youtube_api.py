import html
from io import StringIO
import os
import re
import isodate
import requests
import webvtt
import yt_dlp
from zeeguu.core.util.text import remove_emojis
from langdetect import detect, LangDetectException

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
    # Quota: 100 units per 50 results

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
        "duration": int(
            isodate.parse_duration(item["contentDetails"]["duration"]).total_seconds()
        ),
    }

    if not is_video_language_correct(
        video_info["title"], video_info["description"], lang
    ):
        print(f"Video {video_unique_key} is not in the expected language {lang}.")
        video_info["broken"] = NOT_IN_EXPECTED_LANGUAGE

    if has_dubbed_audio(video_unique_key):
        print(f"Video {video_unique_key} has dubbed audio.")
        video_info["broken"] = DUBBED_AUDIO

    captions = get_captions(video_unique_key, lang)
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


def get_captions(video_unique_key, lang):
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "writesubtitles": True,
        "subtitleslangs": [lang],
        "subtitlesformat": "vtt",
        "cookies": os.getenv("YOUTUBE_COOKIES_FILE_PATH"),
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
                    return parse_vtt(vtt_content)
            return None
        except Exception as e:
            print(f"Error fetching subtitles for {video_unique_key}: {e}")
            return None


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


def clean_vtt(vtt_content):
    vtt_content = html.unescape(vtt_content)
    vtt_content = remove_emojis(vtt_content)
    return vtt_content


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


def has_dubbed_audio(video_unique_key):
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "force_generic_extractor": True,
            "cookies": os.getenv("YOUTUBE_COOKIES_FILE_PATH"),
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

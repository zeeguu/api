from dotenv import load_dotenv
import requests
import os
import json
import yt_dlp
from io import StringIO
import webvtt
import isodate

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

def video_query(search_term, categoryId, lang):

    SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
    VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"

    search_params = {
        "part": "id",
        "videoCategoryId": categoryId,
        "type": "video",
        "videoCaption": "closedCaption",
        "videoEmbeddable": "true",
        "relevanceLanguage": lang,
        "maxResults": 50,
        "key": YOUTUBE_API_KEY,
    }

    response = requests.get(SEARCH_URL, params=search_params)
    search_data = response.json()

    video_ids = [item["id"]["videoId"] for item in search_data.get("items", [])]
    if not video_ids:
        return []


    video_params = {
        "part": "snippet,contentDetails",
        "id": ",".join(video_ids),
        "key": YOUTUBE_API_KEY,
    }

    response = requests.get(VIDEO_URL, params=video_params)
    video_data = response.json()

    videos = []

    for item in video_data.get("items", []):
        video_id = item["id"]
        snippet = item["snippet"]
        content_details = item["contentDetails"]
        
        captions = get_captions(video_id, lang)
        if captions is None:
            continue

        video_info = {
            "videoId": video_id,
            "title": snippet["title"],
            "description": snippet.get("description", ""),
            "publishedAt": snippet["publishedAt"],

            # TODO: find_or_create channel with channel_id then use channel.id as channel_id
            "channelId": snippet["channelId"],
            "thumbnail": snippet["thumbnails"].get("maxres", {}).get("url", "No maxres thumbnail available"),
            "tags": snippet.get("tags", []),
            "duration": int(isodate.parse_duration(content_details["duration"]).total_seconds()),
            "language": lang,
            "vtt": captions["vtt"],
            "text": captions["text"],
            "captions": captions["captions"]
        }

        videos.append(video_info)

        with open("video_result.json", "w", encoding="utf-8") as file:
            json.dump(videos, file, ensure_ascii=False, indent=4)

# def has_manual_captions(video_id, lang):
#     ydl_opts = {
#         "quiet": True,
#         "list_subs": True,
#     }

#     with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#         try:
#             info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
#             subtitles = info.get("subtitles", {})
#             return lang in subtitles
#         except Exception as e:
#             print(f"Error fethcing subtitles for {video_id}: {e}")
#             return False

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
                    return parse_vtt(vtt_content)
            return None
        except Exception as e:
            print(f"Error fethcing subtitles for {video_id}: {e}")
            return None

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

def fetch_channel_info(channel_id, lang):
    CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"
    
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
        "channelName": snippet["title"],
        "description": snippet.get("description", ""),
        "viewCount": statistics["viewCount"],
        "subscriberCount": statistics["subscriberCount"],
        "language": lang,
        #"rss_url": f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}",
    }
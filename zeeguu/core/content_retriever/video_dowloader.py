import requests
import os

import zeeguu.core
from zeeguu.core import model

db_session = zeeguu.core.model.db.session

# TR: Will we use a single API key or multiple ones?
languages = {
    "da": os.getenv("YOUTUBE_API_KEY_DA"),
    "es": os.getenv("YOUTUBE_API_KEY_ES"),
}

YT_TOPIC_IDS = {
    # Sports topics
    # "Sports": "/m/06ntj",
    # Entertainment topics
    #   "Entertainment": "/m/02jjt",
    #   "Humor": "/m/09kqc",
    #   "Movies": "/m/02vxn",
    #   "Performing arts": "/m/05qjc",
    #   # Lifestyle topics
    #   "Lifestyle": "/m/019_rr",
    #   "Fashion": "/m/032tl",
    #   "Fitness": "/m/027x7n",
    #   "Food": "/m/02wbm",
    #   "Hobby": "/m/03glg",
    #   "Pets": "/m/068hy",
    #   "Technology": "/m/07c1v",
    #   "Tourism": "/m/07bxq",
    #   "Vehicles": "/m/07yv9",
    #   # Society topics
    #   "Society (parent topic)": "/m/098wr",
    #   "Business": "/m/09s1f",
    #   "Health": "/m/0kt51",
    #   "Military": "/m/01h6rj",
    #   "Politics": "/m/05qt0",
    #   # Other topics
    #   "Knowledge": "/m/01k8wb",
}

YT_CATEGORY_IDS = {
    # "Film & Animation": 1,
    # "Autos & Vehicles": 2,
    # "Pets & Animals": 15,
    # "Sports": 17,
    # "Travel & Events": 19,
    # "Gaming": 20,
    # "Videoblogging": 21,
    # "People & Blogs": 22,
    # "Comedy": 23,
    "Entertainment": 24,
    # "News & Politics": 25,
    # "Howto & Style": 26,
    # "Education": 27,
    # "Science & Technology": 28,
    # "Nonprofits & Activism": 29,
}


def video_query(lang, api_key, category_id=None, topic_id=None, max_results=50):
    """
    This provides a list of video ids (no video information is provided).

    The actual data extraction is done at fetch_video_info
    """
    if max_results > 50:
        print(
            f"max_results was higher than 50 ({max_results}), Youtube only allows a max of 50..."
        )
    SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

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
        "key": api_key,
    }

    response = requests.get(SEARCH_URL, params=search_params)
    search_data = response.json()

    video_ids = [item["id"]["videoId"] for item in search_data.get("items", [])]
    if not video_ids:
        return []

    return video_ids


def crawl(max_results=50):
    for lang, api_key in languages.items():
        if not api_key:
            print(
                f"API key is None, make sure to add it to environment variables... Value was: {api_key}"
            )
            continue
        print("Crawling language: " + lang)
        for topic_name, topicId in YT_TOPIC_IDS.items():
            print("Crawling topic: " + topic_name)
            video_ids = video_query(
                lang, api_key, topic_id=topicId, max_results=max_results
            )
            for video_id in video_ids:
                print(model.Video.find_or_create(db_session, video_id, lang))

        for category_name, category_id in YT_CATEGORY_IDS.items():
            print("Crawling category: " + category_name)
            video_ids = video_query(
                lang, api_key, category_id=category_id, max_results=max_results
            )
            for video_id in video_ids:
                print(model.Video.find_or_create(db_session, video_id, lang))

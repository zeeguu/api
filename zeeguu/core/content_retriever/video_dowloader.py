import requests
import os

import zeeguu.core
from zeeguu.core import model

db_session = zeeguu.core.model.db.session

from dotenv import load_dotenv
load_dotenv()

languages = {
    "da": os.getenv("YOUTUBE_API_KEY_DA"),
    "es": os.getenv("YOUTUBE_API_KEY_ES"),
}

def video_query(lang, apiKey, categoryId=None, topicId=None):

    SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

    search_params = {
        "part": "id",
        "videoCategoryId": categoryId,
        "topicId": topicId,
        "type": "video",
        "videoCaption": "closedCaption",
        "videoEmbeddable": "true",
        "relevanceLanguage": lang,
        "videoDuration": "medium",
        "maxResults": 50,
        "key": apiKey,
    }

    response = requests.get(SEARCH_URL, params=search_params)
    search_data = response.json()

    video_ids = [item["id"]["videoId"] for item in search_data.get("items", [])]
    if not video_ids:
        return []

    return video_ids

def crawl():
    topicIds = {
        # Sports topics
        "Sports": "/m/06ntj",

        # Entertainment topics
        "Entertainment": "/m/02jjt",
        "Humor": "/m/09kqc",
        "Movies": "/m/02vxn",
        "Performing arts": "/m/05qjc",

        # Lifestyle topics
        "Lifestyle": "/m/019_rr",
        "Fashion": "/m/032tl",
        "Fitness": "/m/027x7n",
        "Food": "/m/02wbm",
        "Hobby": "/m/03glg",
        "Pets": "/m/068hy",
        "Technology": "/m/07c1v",
        "Tourism": "/m/07bxq",
        "Vehicles": "/m/07yv9",

        # Society topics
        "Society (parent topic)": "/m/098wr",
        "Business": "/m/09s1f",
        "Health": "/m/0kt51",
        "Military": "/m/01h6rj",
        "Politics": "/m/05qt0",

        # Other topics
        "Knowledge": "/m/01k8wb"
    }

    categoryIds = {
        "Film & Animation": 1,
        "Autos & Vehicles": 2,
        "Pets & Animals": 15,
        "Sports": 17,
        "Travel & Events": 19,
        "Gaming": 20,
        "Videoblogging": 21,
        "People & Blogs": 22,
        "Comedy": 23,
        "Entertainment": 24,
        "News & Politics": 25,
        "Howto & Style": 26,
        "Education": 27,
        "Science & Technology": 28,
        "Nonprofits & Activism": 29,
    }

    for lang, apiKey in languages.items():
        print("Crawling language: " + lang)
        for topicName, topicId in topicIds.items():
            print("Crawling topic: " + topicName)
            video_ids = video_query(lang, apiKey, topicId=topicId)
            for video_id in video_ids:
                print(model.Video.find_or_create(db_session, video_id, lang))

        for categoryName, categoryId in categoryIds.items():
            print("Crawling category: " + categoryName)
            video_ids = video_query(lang, apiKey, categoryId=categoryId)
            for video_id in video_ids:
                print(model.Video.find_or_create(db_session, video_id, lang))

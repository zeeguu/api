import zeeguu.core
from zeeguu.core import model
from zeeguu.core.youtube_api.youtube_api import get_video_unique_keys

db_session = zeeguu.core.model.db.session

languages = ["da", "es"]

YT_TOPIC_IDS = {
    # Sports topics
    "Sports": "/m/06ntj",
    # Entertainment topics
    # "Entertainment": "/m/02jjt",
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


def get_videos_for_language(lang, max_results):
    print("Getting videos for: " + lang)
    for topic_name, topicId in YT_TOPIC_IDS.items():
        print("Crawling topic: " + topic_name)
        video_ids = get_video_unique_keys(
            lang, topic_id=topicId, max_results=max_results
        )
        for video_id in video_ids:
            print(model.Video.find_or_create(db_session, video_id, lang))
    for category_name, category_id in YT_CATEGORY_IDS.items():
        print("Crawling category: " + category_name)
        video_ids = get_video_unique_keys(
            lang, category_id=category_id, max_results=max_results
        )
        for video_id in video_ids:
            print(model.Video.find_or_create(db_session, video_id, lang))


def crawl(max_results=50):
    for lang in languages:
        get_videos_for_language(lang, max_results)

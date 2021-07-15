from datetime import datetime


import zeeguu.core
from feed_retrieval import retrieve_articles_from_all_feeds
from recompute_recommender_cache import clean_the_cache, recompute_for_users

import logging

logging.getLogger("elasticsearch").setLevel(logging.CRITICAL)

logging.getLogger("zeeguu.core").setLevel(logging.INFO)


start = datetime.now()
zeeguu.core.log(f"started at: {datetime.now()}")

retrieve_articles_from_all_feeds()
clean_the_cache()
recompute_for_users()

end = datetime.now()
zeeguu.core.log(f"done at: {end}")
zeeguu.core.log(f"total duration: {end - start}")

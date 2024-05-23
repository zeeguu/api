from datetime import datetime
import sys


from feed_retrieval import (
    retrieve_articles_from_all_feeds,
    retrieve_articles_for_language,
)

from zeeguu.logging import log

import logging

logging.getLogger("elasticsearch").setLevel(logging.CRITICAL)
logging.getLogger("zeeguu.core").setLevel(logging.INFO)

start = datetime.now()
log(f"started at: {datetime.now()}")
print("LAST VERSION!!!")

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

if len(sys.argv) > 1:
    retrieve_articles_for_language(sys.argv[1], send_email=True)
else:
    retrieve_articles_from_all_feeds()

end = datetime.now()
log(f"done at: {end}")
log(f"total duration: {end - start}")

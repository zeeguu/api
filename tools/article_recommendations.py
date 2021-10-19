from zeeguu.core.content_recommender import article_recommendations_for_user
from zeeguu.core.model import User
import sys


user = User.find_by_id(2953)
print(user.name)

results = article_recommendations_for_user(
    user,
    20,
    sys.argv[1],
    sys.argv[2],
    sys.argv[3],
)

results.sort(key=lambda x: x["published"], reverse=True)

for article in results:

    print(
        article["published"][0:16]
        + " ["
        + article["topics"]
        + "] "
        + article["title"][0:42]
        + "\n"
    )

from zeeguu.core.content_recommender import article_recommendations_for_user
from zeeguu.core.model import User

user = User.find_by_id(2953)
print(user.name)

results = article_recommendations_for_user(
    user,
    20,
    "30d",
    0.8,
    4.2,
)

for article in results:

    print(
        article["published"][0:16]
        + "\n"
        + article["topics"]
        + "\n"
        + article["title"][0:42]
        + "\n"
        + "\n"
    )

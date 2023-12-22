from zeeguu.core.content_quality.quality_filter import sufficient_quality_plain_text
from zeeguu.core.model import Article
from zeeguu.core.model import db

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

article_count = input("How many articles to clean?  ")
article_count = int(article_count)

all_articles = Article.query.filter_by(broken=0).order_by(Article.id.desc()).limit(article_count)
print(
    f"evaluating articles that are not already marked as broken between {all_articles[0].id} and {all_articles[-1].id}")

broken = 0
for each in all_articles:
    sufficient_quality, reason = sufficient_quality_plain_text(each.content)
    if not sufficient_quality:
        each.vote_broken()
        db.session.add(each)
        print("found broken article: " + str(each.id) + " " + each.url.as_string())
        print("reason: " + reason)
        broken += 1

db.session.commit()
print(f"Marked {broken} articles as broken")

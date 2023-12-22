from zeeguu.core.content_quality.quality_filter import sufficient_quality_plain_text
from zeeguu.core.model import Article
from zeeguu.core.model import db

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

all_articles = Article.query.filter_by(broken=0).order_by(Article.id.desc()).limit(50000)

for each in all_articles:
    sufficient_quality, reason = sufficient_quality_plain_text(each.content)
    if not sufficient_quality:
        each.vote_broken()
        db.session.add(each)
        print("found broken article: " + str(each.id) + " " + each.url.as_string())
        print("reason: " + reason)
db.session.commit()

import zeeguu.core
from zeeguu.core.model import Article, UserArticle
from zeeguu.core.model.starred_article import StarredArticle

db_session = zeeguu.core.model.db.session

for sa in StarredArticle.query.all():
    try:
        article = Article.find_or_create(db_session, sa.url.as_string())
        ua = UserArticle.find_or_create(
            db_session, sa.user, article, starred=sa.starred_date
        )
        db_session.add(ua)
        db_session.commit()
        print(f"{sa.starred_date} x {ua.user.name} x {ua.article.title}")
    except Exception as ex:
        print(f"could not import {sa.url.as_string()}")
        print(ex)

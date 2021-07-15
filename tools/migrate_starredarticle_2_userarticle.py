import zeeguu.core
from zeeguu.core.model import Article, UserArticle
from zeeguu.core.model.starred_article import StarredArticle

session = zeeguu.core.db.session

for sa in StarredArticle.query.all():
    try:
        article = Article.find_or_create(session, sa.url.as_string())
        ua = UserArticle.find_or_create(session, sa.user, article, starred=sa.starred_date)
        session.add(ua)
        session.commit()
        print(f'{sa.starred_date} x {ua.user.name} x {ua.article.title}')
    except Exception as ex:
        print(f'could not import {sa.url.as_string()}')
        print(ex)

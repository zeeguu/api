from zeeguu.core.model import Text, Article

import zeeguu.core

texts = zeeguu.core.model.db.session.query(Text).order_by(Text.id.desc()).all()

not_found = 0
found = 1

for text in texts:

    # print(text.article_id)
    if not text.article:

        article_id = None
        if "articleID" in text.url.as_canonical_string():
            article_id = text.url.as_canonical_string().split("articleID=")[-1]
            # print(f'extracted id: {article_id}')

        if article_id:
            article = Article.query.filter_by(id=article_id).one()
        else:
            article = Article.find(text.url.as_canonical_string())
            # print(text.url.as_canonical_string())

        if not article:
            not_found += 1
            print(f"not found: {not_found}")
        else:
            found += 1
            text.article = article
            zeeguu.core.model.db.session.add(text)

            # print(text)
            # print(article)
            # print(text.url.as_string())
            # print(text.article.url.as_string())
            print(f"found: {found}")

        if found % 1500 == 0:
            print("committing 1500 at a time")
            zeeguu.core.model.db.session.commit()

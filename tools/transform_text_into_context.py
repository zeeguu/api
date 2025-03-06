# coding=utf-8
import zeeguu.core
from zeeguu.api.app import create_app
from zeeguu.core.model import Text
from zeeguu.core.model.context import Context, ContextSources
from zeeguu.core.model.article_fragment import ArticleFragment
from tqdm import tqdm
from sqlalchemy import desc

app = create_app()
app.app_context().push()
db_session = zeeguu.core.model.db.session

"""
Each text needs to be converted to a context.
article_id, in_content will now be stored via the bookmark (context_type), and placed into the 
respective mapping table (ArticleFragmentContext or ArticleTitleContext).

The coordinates will be stored in the mapping tables (ArticleFragmentContext, ArticleTitleContext, ...)
However, from the initial mapping the ones in ArticleContent can be placed assuming that the
paragraph_i == order of the fragment.

If NULL, the context is created but the the bookmark is not given a context_type.
"""

ITERATION_STEP = 1000
texts = Text.query.order_by(desc(Text.article_id)).all()
for i, t in tqdm(enumerate(texts), total=len(texts)):
    if len(t.content) > 1000:
        bookmarks = t.all_bookmarks_for_text()
        for b in bookmarks:
            db_session.delete(b)
        continue
    context = Context.find_or_create(
        db_session,
        t.content,
        t.language,
        t.left_ellipsis,
        t.right_ellipsis,
        commit=False,
    )
    db_session.add(context)
    bookmarks = t.all_bookmarks_for_text()
    print(f"Processing text {t.id} with {len(bookmarks)} bookmarks")
    for b in bookmarks:
        b.context = context
        fragment_id = None
        # Give a context type:
        if t.in_content:
            b.context_type = ContextSources.ArticleFragment
            print(t.article_id, t.paragraph_i)
            fragment = ArticleFragment.find_by_article_order(
                t.article_id, t.paragraph_i
            )
            if fragment is None:
                print(f"Fragment not found for article {t.article_id}, skipping..")
                continue
        elif t.in_content == False:
            b.context_type = ContextSources.ArticleTitle
            if t.article is None:
                print(f"Article not found for article {t.article_id}, skipping..")
                continue
        else:
            print(f"No context type found for article {t.article_id}, skipping..")
            print(f"{t.id}, {t.in_content}, {t.article_id}")
            input("Waiting...")
            b.context_type = None

        db_session.add(b)
        if b.context_type is not None:
            b.create_context_mapping(
                db_session,
                t.sentence_i,
                t.token_i,
                fragment,
                t.article,
            )
    if i % ITERATION_STEP == 0 and i > 0:
        print(f"Processed {i} texts")
        db_session.commit()
db_session.commit()

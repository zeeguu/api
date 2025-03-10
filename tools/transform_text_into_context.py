# coding=utf-8
import zeeguu.core
from zeeguu.api.app import create_app
from zeeguu.core.model import Text
from zeeguu.core.model.bookmark_context import BookmarkContext
from zeeguu.core.model.article_fragment import ArticleFragment
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.model.article_fragment_context import ArticleFragmentContext
from zeeguu.core.model.article_title_context import ArticleTitleContext
from tqdm import tqdm
from sqlalchemy import desc

app = create_app()
app.app_context().push()
db_session = zeeguu.core.model.db.session

"""
Each text needs to be converted to a context.
article_id, in_content will now be stored via the bookmark (context_type), and placed into the 
respective mapping table (ArticleFragmentContext or ArticleTitleContext).

The coordinates are stored in the context + bookmark, the mapping tables server only to 
link the bookmark to the original content it came from.
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

    bookmarks = t.all_bookmarks_for_text()
    print(f"Processing text {t.id} with {len(bookmarks)} bookmarks")
    for b in bookmarks:
        context_type = None
        if t.article_id:
            context_type = (
                ContextType.find_by_type(ContextType.ARTICLE_FRAGMENT)
                if t.in_content
                else ContextType.find_by_type(ContextType.ARTICLE_TITLE)
            )
        else:
            context_type = ContextType.find_by_type(ContextType.USER_EDITED)

        context = BookmarkContext.find_or_create(
            db_session,
            t.content,
            context_type,
            t.language,
            t.left_ellipsis,
            t.right_ellipsis,
            commit=False,
        )
        db_session.add(context)
        b.context = context

        fragment_id = None
        db_session.add(b)
        if not t.article_id:
            print(f"{b} did not have an article mapping.")
            continue
        b.source_id = t.article.source_id
        # Give a context type:
        if t.in_content:
            fragment = ArticleFragment.find_by_article_order(
                t.article_id, t.paragraph_i
            )
            if fragment is None:
                print(f"Fragment not found for article {t.article_id}, skipping..")
                continue
            ArticleFragmentContext.find_or_create(db_session, b, fragment, commit=False)
        elif t.in_content == False:
            ArticleTitleContext.find_or_create(db_session, b, t.article, commit=False)
            if t.article is None:
                print(f"Article not found for article {t.article_id}, skipping..")
                continue
        else:
            print(f"No context type found for article {t.article_id}, skipping..")
            print(f"{t.id}, {t.in_content}, {t.article_id}")
        db_session.add(b)

    if i % ITERATION_STEP == 0 and i > 0:
        print(f"Processed {i} texts")
        db_session.commit()
db_session.commit()

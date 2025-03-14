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
from sqlalchemy import asc

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

ACCUMULATED_LOG = ""


def add_to_log(s):
    global ACCUMULATED_LOG
    ACCUMULATED_LOG += f"{s}\n"


ITERATION_STEP = 1000
articles_broken = 0
texts = Text.query.order_by(asc(Text.article_id)).all()
for i, t in tqdm(enumerate(texts), total=len(texts)):
    if len(t.content) > 1000:
        add_to_log(
            f"<Text {t.id} (a:{t.article_id})> was too long (> 1000 chars). Deleting Text and Bookmarks."
        )
        bookmarks = t.all_bookmarks_for_text()
        for b in bookmarks:
            db_session.delete(b)
        db_session.delete(t)
        continue

    bookmarks = t.all_bookmarks_for_text()
    add_to_log(f"Processing text {t.id} with {len(bookmarks)} bookmarks")
    for b in bookmarks:
        context_type = None
        if t.article_id:
            context_type = (
                ContextType.ARTICLE_FRAGMENT
                if t.in_content
                else ContextType.ARTICLE_TITLE
            )
        else:
            context_type = ContextType.USER_EDITED_TEXT

        context = BookmarkContext.find_or_create(
            db_session,
            t.content,
            context_type,
            t.language,
            t.sentence_i,
            t.token_i,
            t.left_ellipsis,
            t.right_ellipsis,
            commit=False,
        )
        db_session.add(context)
        b.context = context

        db_session.add(b)
        if not t.article_id:
            add_to_log(
                f"{b} did not have an article mapping. Considered 'UserEditedText'."
            )
            continue
        elif not t.article.source_id:
            add_to_log(
                f"<Text {t.id} (a:{t.article_id})> did not have a source mapping. Possibly, hasn't been migrated."
            )
            continue
        elif t.article.broken > 0:
            add_to_log(
                f"<Text {t.id} (a:{t.article_id})> article is broken. Consider for deletion."
            )
            articles_broken += 1
            continue

        b.source_id = t.article.source_id
        # Give a context type:
        match context_type:
            case ContextType.ARTICLE_FRAGMENT:
                fragment = ArticleFragment.find_by_article_order(
                    t.article_id, t.paragraph_i
                )
                if fragment is None:
                    add_to_log(
                        f"Fragment (a:{t.article_id}, o: {t.paragraph_i}) not found. This is likely because the article was broken. Skipping..",
                    )
                    continue
                ArticleFragmentContext.find_or_create(
                    db_session, b, fragment, commit=False
                )
            case ContextType.ARTICLE_TITLE:
                ArticleTitleContext.find_or_create(
                    db_session, b, t.article, commit=False
                )
                if t.article is None:
                    add_to_log(
                        f"Article not found for article {t.article_id}, skipping..",
                    )
                    continue
            case _:
                add_to_log(
                    f"No context type found for article {t.article_id}, skipping..",
                )
                add_to_log(f"{t.id}, {t.in_content}, {t.article_id}")
        db_session.add(b)

    if i % ITERATION_STEP == 0 and i > 0:
        print(f"Processed {i} texts")
        print("Log during this batch:")
        print(ACCUMULATED_LOG)
        print("#" * 30)
        ACCUMULATED_LOG = ""
        print("Commiting...")
        db_session.commit()
db_session.commit()
print(f"Total broken articles in the DB: {articles_broken}")

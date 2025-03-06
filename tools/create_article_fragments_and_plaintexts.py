# coding=utf-8
import zeeguu.core
from datetime import datetime
from zeeguu.api.app import create_app
from zeeguu.core.model import Article
from zeeguu.core.model.article_fragment import ArticleFragment
from zeeguu.core.model.plaintext import Plaintext
from tqdm import tqdm
from sqlalchemy import desc

app = create_app()
app.app_context().push()
db_session = zeeguu.core.model.db.session

ITERATION_STEP = 1000


def main():
    """
    This script processes all articles in the Zeeguu database that are not already associated with a plaintext object.
    For each article, it creates a new plaintext object if one does not already exist, and then associates the plaintext
    object with the article by setting the `plaintext` attribute of the article to the newly created plaintext object.
    After processing all articles, it commits the changes to the database.

    The script uses pagination to process articles in batches of 1000 at a time. It also logs progress using tqdm,
    which provides a dynamic progress bar that shows how much of the data has been processed and estimates
    the total time remaining.
    """

    ids_to_filter = [
        fragment[0] for fragment in db_session.query(ArticleFragment.article_id).all()
    ]
    total_articles = Article.query.filter(Article.id.not_in(ids_to_filter)).count()
    for a_offset in tqdm(
        range(0, total_articles, ITERATION_STEP), total=total_articles // ITERATION_STEP
    ):
        articles = (
            Article.query.filter(Article.id.not_in(ids_to_filter))
            .order_by(desc(Article.id))
            .limit(ITERATION_STEP)
            .offset(a_offset)
            .all()
        )
        for a in tqdm(articles, total=len(articles)):
            plaintext = Plaintext.find_or_create(
                db_session, a.content, a.language, commit=False
            )
            a.plaintext = plaintext
            a.create_article_fragments(session=db_session)
        print(f"Processed {a_offset + ITERATION_STEP} articles")
        print(f"Last processed article id: ", a.id)
        db_session.commit()
    db_session.commit()


if __name__ == "__main__":

    start = datetime.now()
    print(f"started at: {start}")
    main()
    end = datetime.now()
    print(f"ended at: {end}")
    print(f"Process took: {end-start}")

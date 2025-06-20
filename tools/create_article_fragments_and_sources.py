# coding=utf-8
import zeeguu.core
from datetime import datetime
from zeeguu.api.app import create_app
from zeeguu.core.model.article import Article
from zeeguu.core.model.source_type import SourceType
from zeeguu.core.model.source import Source
from tqdm import tqdm
from sqlalchemy import asc

app = create_app()
app.app_context().push()
db_session = zeeguu.core.model.db.session

ITERATION_STEP = 1000


def main():
    """
    This script processes all articles in the Zeeguu database that are not already
    associated with a Source object. For each article, it creates a new Source object if
    one does not already exist, and then associates the Source object with the article.

    The script uses pagination to process articles in batches of 1000 at a time. It logs
    progress using tqdm.
    """
    non_migrated_articles_query = Article.query.filter(
        Article.source_id == None
    ).order_by(asc(Article.id))
    total_articles = non_migrated_articles_query.count()
    for a_offset in tqdm(
        range(0, total_articles, ITERATION_STEP), total=total_articles // ITERATION_STEP
    ):
        articles = non_migrated_articles_query.limit(ITERATION_STEP).all()
        ids = [a.id for a in articles]
        print(
            f"Got articles from {a_offset} ({min(ids)}) to {a_offset + ITERATION_STEP} ({max(ids)})"
        )
        for a in tqdm(articles, total=len(articles)):
            source = Source.find_or_create(
                db_session,
                a.get_content(),
                SourceType.find_by_type(SourceType.ARTICLE),
                a.language,
                broken=a.broken,
                commit=False,
            )
            a.source = source
            if a.broken == 0:
                # Only create fragments if the article isn't broken?
                a.create_article_fragments(session=db_session)
        print(f"Processed {a_offset + ITERATION_STEP} articles...")
        print(f"Last processed article id: {a.id}")
        db_session.commit()
    db_session.commit()
    print("Completed... Running query to check for any articles without sources.")
    total_articles_after = non_migrated_articles_query.count()
    print(f"Articles without sources: {total_articles_after}")
    if total_articles_after == 0:
        print("All articles have sources.")
    else:
        print("#" * 20, " INFO ", "#" * 20)
        print("Some articles do not have sources.")


if __name__ == "__main__":

    start = datetime.now()
    print(f"started at: {start}")
    main()
    end = datetime.now()
    print(f"ended at: {end}")
    print(f"Process took: {end-start}")

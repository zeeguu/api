# Script:
#
# remove all articles from the DB which have no
# references to them and are older than a number of days
#
# works with the db that is defined in the configuration
# pointed by zeeguu.core_CONFIG
#
# takes as argument the number of days before which the
# articles will be deleted.
#
# call like this to remove all articles older than 90 days
#
#
#      python remove_unreferenced_articles.py 90
#
#
#
import sqlalchemy
import traceback

from zeeguu.core.model import (
    Article,
    UserArticle,
    UserActivityData,
    UserReadingSession,
    CohortArticleMap,
    
)
from zeeguu.core.model import db

import sys

dbs = db.session

BATCH_COMMIT_SIZE = 5000


def is_the_article_referenced(article, print_reference_info):
    info = UserArticle.find_by_article(article)
    interaction_data = UserActivityData.query.filter_by(article_id=article.id).all()
    reading_session_info = UserReadingSession.query.filter_by(
        article_id=article.id
    ).all()
    belongs_to_a_cohort = CohortArticleMap.query.filter_by(article_id=article.id).all()

    referenced = info or interaction_data or reading_session_info or belongs_to_a_cohort

    if print_reference_info and referenced:
        print(f"WON'T DELETE ID:{article.id} -- {article.title}")

        for ainfo in info:
            print(ainfo.user_info_as_string())

        if interaction_data:
            print("interaction data: (e.g. " + str(interaction_data[0]))

        if reading_session_info:
            print("reading session info: (e.g. " + str(reading_session_info[0]))

        if belongs_to_a_cohort:
            print("referenced by a cohort: (e.g. " + str(belongs_to_a_cohort[0]))

    return referenced


def delete_articles_older_than(DAYS, print_progress_for_every_article=False, delete_from_ES=True):
    print(f"Finding articles older than {DAYS} days...")
    all_articles = Article.all_older_than(days=DAYS)
    print(f" ... article count: {len(all_articles)}")

    i = 0
    referenced_in_this_batch = 0
    deleted = []
    deleted_from_es = 0
    for each in all_articles:
        i += 1
        if print_progress_for_every_article:
            print(f"#{i} -- ID: {each.id}")

        if is_the_article_referenced(each, print_progress_for_every_article):
            referenced_in_this_batch += 1
            continue

        try:
            articles_cache = ArticlesCache.query.filter_by(article_id=each.id).all()
            if articles_cache:
                for each_cache_line in articles_cache:
                    print(
                        f"... ID: {each.id} deleting also cache line: {each_cache_line}"
                    )
                    dbs.delete(each_cache_line)

            deleted.append(each.id)
            dbs.delete(each)

            from zeeguu.core.elastic.indexing import remove_from_index

            if delete_from_ES:
                remove_from_index(each)

            if i % BATCH_COMMIT_SIZE == 0:
                print(
                    f"Keeping {referenced_in_this_batch} articles from the last {BATCH_COMMIT_SIZE} batch..."
                )
                dbs.commit()
                print(
                    f"... the rest of {BATCH_COMMIT_SIZE - referenced_in_this_batch} are now deleted!!!"
                )
                referenced_in_this_batch = 0
                print(f"Deleted from ES index: {deleted_from_es}")
                deleted_from_es = 0

        except sqlalchemy.exc.IntegrityError as e:
            traceback.print_exc()
            dbs.rollback()
            continue

    print(f"Deleted: {deleted}")


if __name__ == "__main__":

    try:
        DAYS = int(sys.argv[1])
    except:
        print(
            "\nOOOPS: you must provide a number of days before which the articles to be deleted\n"
        )
        exit(-1)

    delete_articles_older_than(DAYS, print_progress_for_every_article=False, delete_from_ES=False)

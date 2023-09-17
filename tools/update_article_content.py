import sys
import zeeguu
from zeeguu.api.app import app
from zeeguu.core.model import Article
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
from random import randint
from time import sleep
from sqlalchemy import desc

db_session = zeeguu.core.model.db.session


def update_article(id):
    a = Article.find_by_id(id)
    old_content = a.content
    print(a.title)
    # print(">>>>>> BEFORE <<<<<<")
    # print(a.content)
    a.update_content(session)
    # print("\n\n>>>>>> AFTER <<<<<<\n")
    # print(a.content)
    ZeeguuMailer.send_content_retrieved_notification(a, old_content)


# fr = 7
def update_article_range(start_date, end_date, language_id):
    all = (
        Article.query.filter(Article.language_id == language_id)
        .filter(Article.published_time >= start_date)
        .filter(Article.published_time < end_date)
        .order_by(desc(Article.id))
        .all()
    )
    for each in all:
        try:
            update_article(each.id)
            sleep(randint(10, 70))
        except Exception as e:
            import traceback

            traceback.print_stack()


# fr = 7
def update_articles_below(max_val, min_val, language_id):
    all = (
        Article.query.filter(Article.id <= max_val)
        .filter(Article.id > min_val)
        .filter(Article.language_id == language_id)
        .order_by(desc(Article.id))
        .all()
    )
    for each in all:
        try:
            print(each.id)
            update_article(each.id)
            sleep(randint(10, 70))
        except Exception as e:
            import traceback

            traceback.print_stack()


if __name__ == "__main__":
    id = int(sys.argv[1])
    update_article(id)

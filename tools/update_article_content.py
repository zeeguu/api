import sys
import zeeguu
from zeeguu.core.model import Article
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
from random import randint
from time import sleep
from sqlalchemy import desc
from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session


def update_article(id):
    a = Article.find_by_id(id)
    old_content = a.content
    print("====================================")
    print(a.title)
    print("====================================")
    # print(">>>>>> BEFORE <<<<<<")
    # print(a.content)
    a.update_content(db_session)
    # print("\n\n>>>>>> AFTER <<<<<<\n")
    # print(a.content)
    ZeeguuMailer.send_content_retrieved_notification(a, old_content)


def update_articles(selected_articles):
    for each in selected_articles:
        try:
            print(each.id)
            update_article(each.id)
            sleep_interval = randint(10, 30)
            print(f"sleeping...{sleep_interval}")
            sleep(sleep_interval)
            print("\n\n")

        except Exception as e:
            import traceback
            traceback.print_stack()


# fr = 7
def update_article_range(start_date, end_date, language_id):
    selected_articles = (
        Article.query.filter(Article.language_id == language_id)
        .filter(Article.published_time >= start_date)
        .filter(Article.published_time < end_date)
        .order_by(desc(Article.id))
        .all()
    )

    update_articles(selected_articles)


# fr = 7
def update_articles_below(max_val, min_val, language_id):
    selected_articles = (
        Article.query.filter(Article.id <= max_val)
        .filter(Article.id > min_val)
        .filter(Article.language_id == language_id)
        .order_by(desc(Article.id))
        .all()
    )
    update_articles(selected_articles)


def articles_in_interval(from_date, to_date, language_id):
    return (
        Article.query.filter(Article.published_time > from_date)
        .filter(Article.published_time < to_date)
        .filter(Article.language_id == language_id)
        .order_by(desc(Article.id))
        .all()
    )


def update_artices_in_time_interval(from_date, to_date, language_id):
    selected_articles = articles_in_interval(from_date, to_date, language_id)
    print("Selected articles...")
    print(selected_articles)
    update_articles(selected_articles)


# datetime(2001, 1, 1)


if __name__ == "__main__":
    if len(sys.argv) == 2:
        article_id = int(sys.argv[1])
        update_article(article_id)
    elif len(sys.argv) == 5:
        if sys.argv[1] == "time_interval":
            from datetime import datetime

            from_date = datetime.strptime(sys.argv[2], "%Y-%m-%d")
            print(from_date)
            to_date = datetime.strptime(sys.argv[3], "%Y-%m-%d")
            print(to_date)
            lang_id = sys.argv[4]
            print(lang_id)
            update_artices_in_time_interval(from_date, to_date, lang_id)
    else:
        print("parse error")

import sys
import zeeguu
from zeeguu.api.app import app
from zeeguu.core.model import Article
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
from random import randint
from time import sleep


session = zeeguu.core.db.session


def update_article(id):
    a = Article.find_by_id(id)
    old_content = a.content
    print(">>>>>> BEFORE <<<<<<")
    print(a.content)
    a.update_content(session)
    print("\n\n>>>>>> AFTER <<<<<<\n")
    print(a.content)
    ZeeguuMailer.send_content_retrieved_notification(a, old_content)


def update_article_range(start, end):
    for i in range(start, end):
        update_article(i)
        sleep(randint(10, 70))


if __name__ == '__main__':
    id = int(sys.argv[1])
    update_article(id)

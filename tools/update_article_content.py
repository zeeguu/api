import sys
import zeeguu
from zeeguu.core.model import Article
from zeeguu.api.app import app
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
print(app.config.get("SEND_NOTIFICATION_EMAILS", False))

session = zeeguu.core.db.session


def update_article(id):
    a = Article.find_by_id(id)
    old_content = a.content
    print(">>>>>> BEFORE <<<<<<")
    print(a.content)
    a.update_content(session)
    print("\n\n>>>>>> AFTER <<<<<<\n")
    print(a.content)
    print("before sending the mail")
    ZeeguuMailer.send_content_retrieved_notification(a, old_content)



if __name__ == '__main__':
    id = int(sys.argv[1])
    update_article(id)

import sys
import zeeguu
from zeeguu.core.model import Article, User
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer


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
    u = User.find_by_id(53)
    ZeeguuMailer.send_feedback("Feedback", "lala", "lulu", u)




if __name__ == '__main__':
    id = int(sys.argv[1])
    update_article(id)

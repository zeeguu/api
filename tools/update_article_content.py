import sys
import zeeguu
from zeeguu.core.model import Article
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

    title = f"Updated Content for article {a.id}"
    content = f"https://www.zeeguu.org/read/article?id={a.id}"
    content += a.title + "\n"
    content += a.content
    content += "--------" + "\n"
    content += "--------" + "\n"
    content += "--------" + "\n"
    content += "--------" + "\n"
    content += "OLD CONTENT" + "\n"
    content += old_content

    mailer = ZeeguuMailer(title, content, "mircea.lungu@gmail.com")
    mailer.send()



if __name__ == '__main__':
    id = int(sys.argv[1])
    update_article(id)

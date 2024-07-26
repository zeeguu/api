from zeeguu.core.model import User
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer

def send_mail_new_articles_search(to_email, search):
    body = "\r\n".join([
        "Hi there,",
        " ",
        "There are new articles related to your subscribed search: " + str(search) + ".",
        " ",
        "Cheers,",
        "The Zeeguu Team"
    ])

    emailer = ZeeguuMailer('New articles to your subscribed search', body, to_email)
    emailer.send()
"""
def send_subscription_emails():
    # find all user, which is subscribed to searches and want to receive email.
    # crawl for all users
    #for each user, and the search they want an email to:
    # send_mail_new_articles_search(to_email, search)
"""
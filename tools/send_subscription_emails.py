import datetime
from zeeguu.api import app
from zeeguu.core.content_recommender.elastic_recommender import article_search_for_user
from zeeguu.core.model import User
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
from zeeguu.core.model.search_subscription import SearchSubscription
from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()


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

def send_subscription_emails():
    all_subscriptions = SearchSubscription.query.filter_by(receive_email=True).all()
    current_datetime = datetime.now(datetime.timezone.utc)
    previous_day_datetime = current_datetime - datetime.timedelta(days=1)

    for subscription in all_subscriptions:
        articles = article_search_for_user(subscription.user_id, 2, subscription.search, page = 0)
        new_articles_found = [article for article in articles if article.published > previous_day_datetime]

        if new_articles_found:
            user = User.find_by_id(subscription.user_id)
            send_mail_new_articles_search(user.email, subscription.search)
            print(f"""
                ####################################
                  email send to {user.email} for: {subscription.search}
                ###################################
        """)
        else:
            print(f"""
                ####################################
                  No new articles found {subscription.search}
                ###################################
        """)

if __name__ == "__main__":
    send_subscription_emails()

    #python article_crawler.py da
    #_plaground
    #move to tools...
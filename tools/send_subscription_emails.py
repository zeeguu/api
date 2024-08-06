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
    body = "\r\n".join(
        [
            "Hi there,",
            " ",
            "There are new articles related to your subscribed search: "
            + str(search)
            + ".",
            " ",
            "You can find your subscriptions here: https://www.zeeguu.org/articles/mySearches"
            " ",
            "Cheers,",
            "The Zeeguu Team",
        ]
    )
    print(f"""Sending to '{to_email}': ''{body}''""")
    emailer = ZeeguuMailer("New articles to your subscribed search", body, to_email)
    emailer.send()


def send_subscription_emails():
    all_subscriptions = SearchSubscription.query.filter_by(receive_email=True).all()
    current_datetime = datetime.datetime.now()
    previous_day_datetime = current_datetime - datetime.timedelta(days=1)
    user_subscriptions = {}
    for subscription in all_subscriptions:
        user = User.find_by_id(subscription.user_id)
        articles = article_search_for_user(
            user, 2, subscription.search.keywords, page=0
        )
        new_articles_found = [
            article
            for article in articles
            if article.published_time > previous_day_datetime
        ]
        if new_articles_found:
            user_subscriptions[user.email] = user_subscriptions.get(user.email, []) + [
                subscription.search.keywords
            ]
    for user_email, keywords in  user_subscriptions.items():
        send_mail_new_articles_search(user_email, f"'{"','".join(keywords)}'")


if __name__ == "__main__":
    send_subscription_emails()

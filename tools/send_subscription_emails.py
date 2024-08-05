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
            "There are new articles related to your subscribed search: {search}"
            + ".",
            "You can see them on the link below:",
            "https://www.zeeguu.org/search?search={search}",
            " ",
            "Cheers,",
            "The Zeeguu Team",
        ]
    )

    emailer = ZeeguuMailer("New articles about " + str(search), body, to_email)
    emailer.send()


def send_subscription_emails():
    all_subscriptions = SearchSubscription.query.filter_by(receive_email=True).all()
    current_datetime = datetime.datetime.now()
    previous_day_datetime = current_datetime - datetime.timedelta(days=1)

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

            send_mail_new_articles_search(user.email, subscription.search.keywords)
            print(
                f"""
                ####################################
                  email send to {user.email} for: {subscription.search.keywords}
                ###################################
        """
            )
        else:
            print(
                f"""
                ####################################
                  No new articles found {subscription.search.keywords} for user: {user.email}
                ###################################
        """
            )


if __name__ == "__main__":
    send_subscription_emails()

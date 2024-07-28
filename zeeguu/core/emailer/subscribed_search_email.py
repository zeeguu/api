import datetime
from zeeguu.api import app
from zeeguu.core.content_recommender.elastic_recommender import article_search_for_user
from zeeguu.core.model import User
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
from zeeguu.core.model.search import Search
from zeeguu.core.model.search_subscription import SearchSubscription
from apscheduler.schedulers.background import BackgroundScheduler


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
    all_searches = Search.query.all()
    current_datetime = datetime.now(datetime.timezone.utc)
    previous_day_datetime = current_datetime - datetime.timedelta(days=1)

    for subscription in all_subscriptions:
        for search in all_searches:
            if subscription.search_id == search.id:
                articles = article_search_for_user(subscription.user_id, 2, search.keywords, page = 0)
                new_articles_found = [article for article in articles if article.published > previous_day_datetime]

                if new_articles_found:
                    user = User.find_by_id(subscription.user_id)
                    send_mail_new_articles_search(user.email, search)

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_subscription_emails, 'cron', hour=8, minute=0)
    scheduler.start()

if __name__ == "__main__":
    start_scheduler()
    app.run(debug=True)
import datetime
from zeeguu.api import app
from zeeguu.core.content_recommender.elastic_recommender import article_search_for_user
from zeeguu.core.model import User
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
from zeeguu.core.model.search_subscription import SearchSubscription
from zeeguu.api.app import create_app
from zeeguu.core.util.reading_time_estimator import estimate_read_time

app = create_app()
app.app_context().push()

def format_article_info(article):
    art_info = article.article_info()
    return f""" <li><p><b>{art_info["title"]}</b></p></li>
                <p>&nbsp;&nbsp;{estimate_read_time(art_info["metrics"]["word_count"])}min, {art_info["metrics"]["cefr_level"]}, <a href="{art_info["url"]}">read</a> on <a href="{article.feed.url.domain.domain_name}">{article.feed.url.domain.domain_name}</a></p>"""


def send_mail_new_articles_search(to_email, name, new_content_dict):
    body = f"""
            <p>Hi {name},</p>
            <p>There are new articles related to your subscribed {"searches" if len(new_content_dict) > 1 else "search"}.</p>
           """
    
    for keyword, articles in new_content_dict.items():
        body += f"""<h3>{keyword}</h3>
                  <hr>"""
        body += f"""<ul>{"".join([format_article_info(a) for a in articles])}</ul>"""
    
    body += f"""
        <p>Find the rest of your subscriptions at: https://www.zeeguu.org/articles/mySearches</p>
        <p>Your Friendly Zeeguu Team.</p>
       """
    
    subject = f"New articles for {"'" + "','".join(new_content_dict.keys()) + "'"}"
    print(body)
    emailer = ZeeguuMailer(subject, body, to_email)
    emailer.send()


def send_subscription_emails():
    all_subscriptions = SearchSubscription.query.filter_by(receive_email=True).all()
    current_datetime = datetime.datetime.now()
    previous_day_datetime = current_datetime - datetime.timedelta(days=1)
    user_subscriptions = {}
    for subscription in all_subscriptions:
        user = User.find_by_id(subscription.user_id)
        # Use the same query as in the MySearches
        articles = article_search_for_user(
            user,
            3,
            subscription.search.keywords,
            page=0,
            use_published_priority=True,
            use_readability_priority=True,
            score_threshold=2,
        )
        new_articles_found = [
            article
            for article in articles
            if article.published_time > previous_day_datetime
        ]
        if new_articles_found:
            updated_dict = user_subscriptions.get((user.email, user.name), {})
            updated_dict[subscription.search.keywords] = [article for article in new_articles_found]
            user_subscriptions[(user.email, user.name)] = updated_dict
    for (email, name), new_content_dict in user_subscriptions.items():
        send_mail_new_articles_search(email, name, new_content_dict)

if __name__ == "__main__":
    send_subscription_emails()

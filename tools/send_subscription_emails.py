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

def remove_protocolfrom_link(link):
    PATTERNS_TO_REMOVE = [
        "http://www.",
        "https://www.",
        "www.",
        "https://",
        "http://"
    ]
    filtered_link = link
    for pattern in PATTERNS_TO_REMOVE:
        filtered_link = filtered_link.replace(pattern, "")
    return filtered_link

def format_article_info(article):
    art_info = article.article_info()
    return f""" <li><b>{art_info["title"]}</b> ({estimate_read_time(art_info["metrics"]["word_count"])}min, {art_info["metrics"]["cefr_level"]}, <a href="{art_info["url"]}">read</a> on <a href="{article.feed.url.domain.domain_name}" style="text-decoration: none; color:black;">{remove_protocolfrom_link(article.feed.url.domain.domain_name)}</a>)</li>"""

def send_mail_new_articles_search(to_email, name, new_content_dict):
    body = f"""
            Hi {name},
            There are new articles containg the {"keywords" if len(new_content_dict) > 1 else "keyword"} you are subscribed to:
           """
    
    for keyword, articles in new_content_dict.items():
        body += f"""<h3 style="color: #2F77AD;">{keyword}</h3><hr style="background-color: rgb(255, 187, 84); height: 1px; border: 0; height: 2px; margin-top: -6px;">"""
        body += f"""<ul>{"".join([format_article_info(a) for a in articles])}</ul>"""
    
    body += f"""
        Find the rest of your subscriptions at: <a href="https://www.zeeguu.org/articles/mySearches">zeeguu.org/articles/mySearches</a>
        Your Friendly Zeeguu Team
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

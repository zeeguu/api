#!/usr/bin/env python
import sys
import os
import random
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# REQUIRED: Initialize Flask app context for database access
from zeeguu.api.app import create_app
from zeeguu.core.model import db
app = create_app()
app.app_context().push()

from zeeguu.core.model.article import Article
from zeeguu.core.model.language import Language
from zeeguu.core.model.url import Url
from zeeguu.core.model.domain_name import DomainName
from zeeguu.core.model.source import Source
from zeeguu.core.model.source_text import SourceText
from zeeguu.core.model.source_type import SourceType
from zeeguu.core.model.user import User
from zeeguu.core.model.user_article import UserArticle
from zeeguu.core.model.friend import Friend
import nltk


def ensure_nltk_resources():
    required_resources = [
        ("tokenizers/punkt_tab", "punkt_tab"),
        ("tokenizers/punkt", "punkt"),
    ]
    for resource_path, resource_name in required_resources:
        try:
            nltk.data.find(resource_path)
        except LookupError:
            nltk.download(resource_name, quiet=True)

# Helper functions for fake data
def random_title():
    titles = [
        "Breaking News: AI Revolutionizes Tech",
        "10 Tips for Learning Languages Fast",
        "The Secret Life of Otters",
        "How to Cook the Perfect Pasta",
        "Exploring the Wonders of Space",
        "The Rise of Electric Vehicles",
        "Why Reading is Good for You",
        "A Guide to Mindfulness Meditation",
        "The History of the Internet",
        "Traveling on a Budget: Top Destinations"
    ]
    return random.choice(titles) + f" #{random.randint(1, 10000)}"

def random_authors():
    first = ["Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Jamie", "Robin", "Drew", "Avery"]
    last = ["Smith", "Johnson", "Lee", "Brown", "Garcia", "Martinez", "Davis", "Clark", "Lewis", "Walker"]
    return f"{random.choice(first)} {random.choice(last)}"

def random_content():
    sentences = [
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        "Vestibulum ac diam sit amet quam vehicula elementum.",
        "Curabitur non nulla sit amet nisl tempus convallis.",
        "Vivamus magna justo, lacinia eget consectetur sed, convallis at tellus.",
        "Pellentesque in ipsum id orci porta dapibus.",
        "Proin eget tortor risus.",
        "Nulla porttitor accumsan tincidunt.",
        "Mauris blandit aliquet elit, eget tincidunt nibh pulvinar a.",
        "Quisque velit nisi, pretium ut lacinia in, elementum id enim.",
        "Donec sollicitudin molestie malesuada."
    ]
    return " ".join(random.choices(sentences, k=random.randint(10, 30)))

def random_url():
    domains = ["example.com", "news.com", "blog.org", "site.net", "demo.io"]
    paths = ["/article", "/news", "/post", "/story", "/feature"]
    return f"https://{random.choice(domains)}{random.choice(paths)}/{random.randint(1000,99999)}"


def random_datetime_in_last_month():
    now = datetime.now()
    start = now - timedelta(days=30)
    return start + timedelta(
        seconds=random.randint(0, int((now - start).total_seconds()))
    )


def get_target_users_for_user_article(target_user_id=5, fallback_count=5):
    target_user = User.query.filter_by(id=target_user_id).first()
    if not target_user:
        return User.query.order_by(User.id.desc()).limit(fallback_count).all()

    users = [target_user]
    users.extend(Friend.get_friends(target_user_id))

    unique_by_id = {}
    for user in users:
        unique_by_id[user.id] = user

    return list(unique_by_id.values())


def create_fake_user_article_rows(articles, target_user_id=5):
    users = get_target_users_for_user_article(target_user_id=target_user_id)
    if not users or not articles:
        return 0

    created = 0
    for article in articles:
        max_users_for_article = min(len(users), random.randint(1, 4))
        selected_users = random.sample(users, max_users_for_article)

        for user in selected_users:
            completed_at = random_datetime_in_last_month()
            opened = completed_at - timedelta(minutes=random.randint(1, 15))
            liked = random.random() < 0.45
            reading_completion = round(random.uniform(0.9, 1.0), 2)

            existing = UserArticle.find(user, article)
            if existing:
                continue

            ua = UserArticle(
                user=user,
                article=article,
                opened=opened,
                liked=liked,
                reading_completion=reading_completion,
                completed_at=completed_at,
            )
            db.session.add(ua)
            created += 1

    db.session.commit()
    return created



def main():
    ensure_nltk_resources()
    num_articles = 100
    created_articles = []
    for _ in range(num_articles):
        title = random_title()
        authors = random_authors()
        content = random_content()
        url_str = random_url()
        domain = DomainName.get_domain(url_str)
        domain_obj = DomainName.query.filter_by(domain_name=domain).first()
        if not domain_obj:
            domain_obj = DomainName(url_str)
            db.session.add(domain_obj)
            db.session.commit()
        url_obj = Url(url_str, title, domain_obj)
        db.session.add(url_obj)
        db.session.commit()
        language = Language.find_or_create('en')
        # print(f"Selected language: {language}, code: {getattr(language, 'code', None)}")
        source_text = SourceText.find_or_create(db.session, content)
        source_type = SourceType.query.filter_by(type=SourceType.ARTICLE).first()
        if not source_type:
            source_type = SourceType(SourceType.ARTICLE)
            db.session.add(source_type)
            db.session.commit()
        source = Source.find_or_create(db.session, content, source_type, language, broken=0)
        summary = content[:200]
        published_time = datetime.now() - timedelta(days=random.randint(0, 30))
        article = Article(
            url=url_obj,
            title=title,
            authors=authors,
            source=source,
            summary=summary,
            published_time=published_time,
            feed=None,
            language=language,
            htmlContent=content,
            uploader=None,
            found_by_user=0,
            broken=0,
            deleted=0,
            video=0,
            img_url=None
        )
        db.session.add(article)
        created_articles.append(article)
    db.session.commit()

    created_user_articles = create_fake_user_article_rows(created_articles)

    print(f"Created {len(created_articles)} fake articles.")
    print(f"Created {created_user_articles} fake user-article rows.")

if __name__ == "__main__":
    main()

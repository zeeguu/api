"""

    Goes through all the interesting sources that the server knows
    about and downloads new articles saving them in the DB.  


"""

import newspaper
import re

import zeeguu_core
from zeeguu_core import log, debug

from zeeguu_core import model
from zeeguu_core.content_retriever.content_cleaner import cleanup_non_content_bits
from zeeguu_core.content_retriever.quality_filter import sufficient_quality
from zeeguu_core.content_retriever.unicode_normalization import flatten_composed_unicode_characters
from zeeguu_core.model import Url, RSSFeed, LocalizedTopic, ArticleWord
import requests

from elasticsearch import Elasticsearch
from zeeguu_core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from zeeguu_core.elastic.converting_from_mysql import document_from_article
from zeeguu_core.model.article import MAX_CHAR_COUNT_IN_SUMMARY

LOG_CONTEXT = "FEED RETRIEVAL"


class SkippedForTooOld(Exception):
    pass


class SkippedForLowQuality(Exception):
    def __init__(self, reason):
        self.reason = reason


class SkippedAlreadyInDB(Exception):
    pass


def _url_after_redirects(url):
    # solve redirects and save the clean url
    response = requests.get(url)
    return response.url


def _date_in_the_future(time):
    from datetime import datetime
    return time > datetime.now()


def download_from_feed(feed: RSSFeed, session, limit=1000, save_in_elastic=True):
    """

        Session is needed because this saves stuff to the DB.


        last_crawled_time is useful because otherwise there would be a lot of time
        wasted trying to retrieve the same articles, especially the ones which
        can't be retrieved, so they won't be cached.


    """

    downloaded = 0
    skipped_due_to_low_quality = 0
    skipped_already_in_db = 0

    last_retrieval_time_from_DB = None
    last_retrieval_time_seen_this_crawl = None

    if feed.last_crawled_time:
        last_retrieval_time_from_DB = feed.last_crawled_time
        log(f"LAST CRAWLED::: {last_retrieval_time_from_DB}")

    try:
        items = feed.feed_items(last_retrieval_time_from_DB)
    except Exception as e:
        log(f"Failed to download feed ({e})")
        from sentry_sdk import capture_exception
        capture_exception(e)
        return

    for feed_item in items:

        skipped_already_in_db = 0

        if downloaded >= limit:
            break

        feed_item_timestamp = feed_item['published_datetime']

        if _date_in_the_future(feed_item_timestamp):
            log("Article from the future!")
            continue

        if (not last_retrieval_time_seen_this_crawl) or (feed_item_timestamp > last_retrieval_time_seen_this_crawl):
            last_retrieval_time_seen_this_crawl = feed_item_timestamp

        if last_retrieval_time_seen_this_crawl > feed.last_crawled_time:
            feed.last_crawled_time = last_retrieval_time_seen_this_crawl
            log(f"+updated feed's last crawled time to {last_retrieval_time_seen_this_crawl}")

        session.add(feed)
        session.commit()

        try:
            new_article = download_feed_item(session,
                                             feed,
                                             feed_item)
            downloaded += 1
        except SkippedForTooOld:
            log("- Article too old")
            continue
        except SkippedForLowQuality as e:
            log(f" - Low quality: {e.reason}")
            skipped_due_to_low_quality += 1
            continue
        except SkippedAlreadyInDB:
            skipped_already_in_db += 1
            log(" - Already in DB")
            continue

        except Exception as e:
            from sentry_sdk import capture_exception
            capture_exception(e)

            if hasattr(e, 'message'):
                log(e.message)
            else:
                log(e)
            continue

        # Saves the news article at ElasticSearch.
        # We recommend that everything is stored both in SQL and Elasticsearch
        # as ElasticSearch isn't persistent data
        try:
            if save_in_elastic:
                if new_article:
                    es = Elasticsearch(ES_CONN_STRING)
                    doc = document_from_article(new_article, session)
                    res = es.index(index=ES_ZINDEX, id=new_article.id, body=doc)
                    print("elastic res: " + res['result'])
        except Exception as e:
            from sentry_sdk import capture_exception
            capture_exception(e)

            log("***OOPS***: ElasticSearch seems down?")
            if hasattr(e, 'message'):
                log(e.message)
            else:
                log(e)
            continue

    log(f'*** Downloaded: {downloaded} From: {feed.title}')
    log(f'*** Low Quality: {skipped_due_to_low_quality}')
    log(f'*** Already in DB: {skipped_already_in_db}')
    log(f'*** ')


def download_feed_item(session,
                       feed,
                       feed_item):
    new_article = None

    try:

        url = _url_after_redirects(feed_item['url'])
        log(url)

    except requests.exceptions.TooManyRedirects:
        raise Exception(f"- Too many redirects")
    except Exception:
        raise Exception(f"- Could not get url after redirects for {feed_item['url']}")

    title = feed_item['title']

    published_datetime = feed_item['published_datetime']

    try:
        art = model.Article.find(url)
    except:
        import sys
        ex = sys.exc_info()[0]
        raise Exception(f" {LOG_CONTEXT}: For some reason excepted during Article.find \n{str(ex)}")

    if art:
        raise SkippedAlreadyInDB()

    try:

        art = newspaper.Article(url)
        art.download()
        art.parse()

        debug("- Succesfully parsed")

        cleaned_up_text = cleanup_non_content_bits(art.text)

        cleaned_up_text = flatten_composed_unicode_characters(cleaned_up_text)

        is_quality_article, reason = sufficient_quality(art)

        if not is_quality_article:
            raise SkippedForLowQuality(reason)

        summary = feed_item['summary']
        # however, this is not so easy... there have been cases where
        # the summary is just malformed HTML... thus we try to extract
        # the text:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(summary, "lxml")
        summary = soup.get_text()
        # then there are cases where the summary is huge... so we clip it
        summary = summary[: MAX_CHAR_COUNT_IN_SUMMARY]
        # and if there is still no summary, we simply use the beginning of
        # the article
        if len(summary) < 10:
            summary = cleaned_up_text[: MAX_CHAR_COUNT_IN_SUMMARY]

            # Create new article and save it to DB
        new_article = zeeguu_core.model.Article(
            Url.find_or_create(session, url),
            title,
            ', '.join(art.authors),
            cleaned_up_text,
            summary,
            published_datetime,
            feed,
            feed.language
        )
        session.add(new_article)

        topics = add_topics(new_article, session)
        log(f" Topics ({topics})")

        add_searches(title, url, new_article, session)
        debug(" Added keywords")

        session.commit()
        log(f"SUCCESS for: {new_article.title}")

    except SkippedForLowQuality as e:
        raise e

    except Exception as e:
        from sentry_sdk import capture_exception
        capture_exception(e)

        log(f"* Rolling back session due to exception while creating article and attaching words/topics: {str(e)}")
        session.rollback()

    return new_article


def add_topics(new_article, session):
    topics = []
    for loc_topic in LocalizedTopic.query.all():
        if loc_topic.language == new_article.language and loc_topic.matches_article(new_article):
            topics.append(loc_topic.topic.title)
            new_article.add_topic(loc_topic.topic)
            session.add(new_article)
    return topics


def add_searches(title, url, new_article, session):
    """
    This method takes the relevant keywords from the title
    and URL, and tries to properly clean them.
    It finally adds the ArticleWord to the session, to be committed as a whole.
    :param title: The title of the article
    :param url: The url of the article
    :param new_article: The actual new article
    :param session: The session to which it should be added.
    """

    # Split the title, path and url netloc (sub domain)
    all_words = title.split()
    from urllib.parse import urlparse

    # Parse the URL so we can call netloc and path without a lot of regex
    parsed_url = urlparse(url)
    all_words += re.split('; |, |\*|-|%20|/', parsed_url.path)
    all_words += parsed_url.netloc.split('.')[0]

    for word in all_words:
        # Strip the unwanted characters
        word = strip_article_title_word(word)
        # Check if the word is of proper length, not only digits and not empty or www
        if word in ['www', '', ' '] or word.isdigit() or len(word) < 3 or len(word) > 25:
            continue
        else:
            # Find or create the ArticleWord and add it to the session
            article_word_obj = ArticleWord.find_by_word(word)
            if article_word_obj is None:
                article_word_obj = ArticleWord(word)
            article_word_obj.add_article(new_article)
            session.add(article_word_obj)


def strip_article_title_word(word: str):
    """

        Used when tokenizing the titles of articles
        in order to index them for search

    """
    return word.strip('":;?!<>\'').lower()

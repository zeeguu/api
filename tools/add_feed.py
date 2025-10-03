#!/usr/bin/env python
import argparse
from zeeguu.api.app import create_app
from zeeguu.core.model import Feed, Url, Language
from zeeguu.core.feed_handler import FEED_TYPE
import zeeguu.core

app = create_app()
app.app_context().push()


def create_and_test_feed(url: str, feed_type: int, test_feed: bool):
    feed = Feed.from_url(url, feed_type=feed_type)
    if test_feed:
        print(feed.feed_health_info())

    return feed


def main():
    parser = argparse.ArgumentParser(description='Add an RSS feed to Zeeguu')
    parser.add_argument('--url', help='Feed URL')
    parser.add_argument('--feed-type', type=int, help=f'Feed type: {FEED_TYPE}')
    parser.add_argument('--name', help='Feed name')
    parser.add_argument('--description', help='Feed description')
    parser.add_argument('--icon', help='Icon filename')
    parser.add_argument('--language', help='Language code (e.g., fr, en)')
    parser.add_argument('--test', action='store_true', help='Test parsing the feed')

    args = parser.parse_args()

    # Interactive mode if no URL provided
    if not args.url:
        _feed_url = input("Feed url:  ")
        print(f"Available feed types: '{FEED_TYPE}'")
        feed_type = int(input("What feed type is it? : "))
        test_feed = input("Do you want to test to parse the feed (1=yes, else n) : ") == "1"
    else:
        _feed_url = args.url
        feed_type = args.feed_type if args.feed_type is not None else int(input(f"Feed type {FEED_TYPE}: "))
        test_feed = args.test

    feed = create_and_test_feed(_feed_url, feed_type, test_feed)

    if args.name:
        feed_name = args.name
    else:
        feed_name = input(f"Feed name (Enter for: {feed.title}):  ") or feed.title
    print(f"= {feed_name}")

    default_icon_name = f"{feed_name.lower().replace(' ', '-')}.png"
    if args.icon:
        icon_name = args.icon
    else:
        icon_name = (
            input(
                f"Icon name to be found in resources folder (e.g. {default_icon_name}):  "
            )
            or default_icon_name
        )
    print(f"= {icon_name}")

    if args.description:
        description = args.description
    else:
        description = (
            input(f"Description (Enter for: {feed.description}): ") or feed.description
        )
    print(f"= {description}")

    if args.language:
        _language = args.language
    else:
        _language = input("Language code (e.g. en): ")
    print(f"= {_language}")

    feed_url = Url.find_or_create(zeeguu.core.model.db.session, _feed_url)
    language = Language.find_or_create(_language)

    feed = Feed.find_or_create(
        zeeguu.core.model.db.session,
        feed_url,
        feed_name,
        description,
        icon_name=icon_name,
        language=language,
        feed_type=feed_type,
    )

    print("Done: ")
    print(feed.title)
    print(feed.description)
    print(feed.language_id)
    print(feed.url.as_string())


if __name__ == "__main__":
    main()

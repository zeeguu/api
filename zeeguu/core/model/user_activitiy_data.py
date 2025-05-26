import json
from datetime import datetime, timedelta
from time import sleep

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, desc
from sqlalchemy.orm import relationship
from zeeguu.core.model.user_reading_session import ALL_ARTICLE_INTERACTION_ACTIONS
from collections import Counter

from zeeguu.logging import log

import sqlalchemy

from zeeguu.core.model import User, Url
from zeeguu.core.model.article import Article
from zeeguu.core.model.source import Source
from zeeguu.core.constants import (
    JSON_TIME_FORMAT,
    EVENT_LIKE_ARTICLE,
    EVENT_USER_FEEDBACK,
    EVENT_USER_SCROLL,
    EVENT_USER_CLICKED_ARTICLE,
)
from zeeguu.core.behavioral_modeling import (
    find_last_reading_percentage,
)
import zeeguu

from zeeguu.core.model.db import db


class UserActivityData(db.Model):
    __table_args__ = dict(mysql_collate="utf8_bin")
    __tablename__ = "user_activity_data"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey(User.id))
    user = relationship(User)

    time = Column(DateTime)

    event = Column(String(255))
    value = Column(String(255))
    extra_data = Column(String(4096))

    source_id = Column(Integer, ForeignKey(Source.id))
    source = relationship(Source)

    def __init__(
        self,
        user,
        time,
        event,
        value,
        extra_data,
        source_id: int = None,
    ):
        self.user = user
        self.time = time
        self.event = event
        self.value = value
        self.extra_data = extra_data
        self.source_id = source_id

    def data_as_dictionary(self):
        data = dict(
            user_id=self.user_id,
            time=self.time.strftime("%Y-%m-%dT%H:%M:%S"),
            event=self.event,
            value=self.value,
            extra_data=self.extra_data,
        )
        if self.source_id:
            data["source_id"] = self.source_id
        return data

    def is_like(self):
        return self.event == EVENT_LIKE_ARTICLE

    def is_feedback(self):
        return self.event == EVENT_USER_FEEDBACK

    def _extra_data_filter(self, attribute_name: str):
        """
            required by .find()
            used to parse extra_data to find a specific attribute

            example of extra_data:

                 {"80":[{"title":"Tour de France - Pourquoi n'ont-ils pas attaqué Froome après son tout-droit","url":"https://www.lequipe.fr/Cyclisme-sur-route/Actualites/Pourquoi-n-ont-ils-pas-attaque-froome-apres-son-tout-droit/818035#xtor=RSS-1","content":"","summary"…

        :param attribute_name -- e.g. "title" in the above exaxmple
        :return: value of attribute
        """
        start = (
            str(self.extra_data).find('"' + attribute_name + '":')
            + len(attribute_name)
            + 4
        )
        end = str(self.extra_data)[start:].find('"')
        return str(self.extra_data)[start : end + start]

    @classmethod
    def _filter_by_extra_value(cls, events, extra_filter, extra_value):
        # TODO: To delete this... i don't think it's ever used
        """

            required by .find()

        :param events:
        :param extra_filter:
        :param extra_value:
        :return:
        """
        filtered_results = []

        for event in events:
            extradata_value = event._extra_data_filter(extra_filter)
            if extradata_value == extra_value:
                filtered_results.append(event)
        return filtered_results

    @classmethod
    def find_or_create(cls, session, user, time, event, value, extra_data, source_id):
        try:
            log("found existing event; returning it instead of creating a new one")
            return (
                cls.query.filter_by(user=user)
                .filter_by(time=time)
                .filter_by(event=event)
                .filter_by(value=value)
                .one()
            )
        except sqlalchemy.orm.exc.MultipleResultsFound:
            return (
                cls.query.filter_by(user=user)
                .filter_by(time=time)
                .filter_by(event=event)
                .filter_by(value=value)
                .first()
            )
        except sqlalchemy.orm.exc.NoResultFound:
            try:
                new = cls(user, time, event, value, extra_data, source_id)
                session.add(new)
                session.commit()
                return new
            except sqlalchemy.exc.IntegrityError:
                for _ in range(10):
                    try:
                        session.rollback()
                        ev = (
                            cls.query.filter_by(user=user)
                            .filter_by(time=time)
                            .filter_by(event=event)
                            .one()
                        )
                        print("successfully avoided race condition. nice! ")
                        return ev
                    except sqlalchemy.orm.exc.NoResultFound:
                        sleep(0.3)
                        continue

    @classmethod
    def find(
        cls,
        user: User = None,
        source: Source = None,
        extra_filter: str = None,
        extra_value: str = None,  # TODO: to delete this, i don't think it's ever used.
        event_filter: str = None,
        only_latest=False,
        source_id: int = None,
    ):
        """

            Find one or more user_activity_data by any of the above filters

        :return: object or None if not found
        """
        query = cls.query

        if source is not None:
            query = query.filter(cls.source == source)
        if event_filter is not None:
            query = query.filter(cls.event == event_filter)
        if user is not None:
            query = query.filter(cls.user == user)
        if source_id is not None:
            query = query.filter(cls.source_id == source_id)
        query = query.order_by("time")

        try:
            events = query.all()
            if extra_filter is None or extra_value is None:
                if only_latest:
                    return events[0]
                else:
                    return events

            filtered = cls._filter_by_extra_value(events, extra_filter, extra_value)
            if only_latest:
                return filtered[0]
            else:
                return filtered
        except:
            return None

    def find_url_in_extra_data(self):
        """
        DB structure is a mess!
        There is no convention where the url associated with an event is.
        Thu we need to look for it in different places

        NOTE: This can be solved by creating a new column called url and write the url only there

        returns: url if found or None otherwise
        """

        if self.extra_data and self.extra_data != "{}" and self.extra_data != "null":
            try:
                extra_event_data = json.loads(self.extra_data)

                if "articleURL" in extra_event_data:
                    url = extra_event_data["articleURL"]
                elif "url" in extra_event_data:
                    url = extra_event_data["url"]
                else:  # There is no url
                    return None
                return Url.extract_canonical_url(url)

            except:  # Some json strings are truncated and some other times extra_event_data is an int
                # therefore cannot be parsed correctly and throw an exception
                return None
        else:  # The extra_data field is empty
            return None

    def _find_article_in_value_or_extra_data(self, db_session):
        """
        Finds or creates an article_id

        return: articleID or NONE

        NOTE: When the article cannot be downloaded anymore,
        either because the article is no longer available or the newspaper.parser() fails

        """

        if self.event in ALL_ARTICLE_INTERACTION_ACTIONS:
            if self.value.startswith("http"):
                url = self.value
            else:
                url = self.find_url_in_extra_data()

            if url:
                return Article.find_or_create(db_session, url).id

        return None

    def get_article_id(self, db_session):
        """

            returns the article_id for those events that have it.

            for those that don't have it, falls back on the old
            way of getting this information which is needed for
            the events in the DB before 2018-08-10

        :param db_session: needed for the old way which creates
        the article if it's not there already

        :return: article ID or None

        """
        if self.article_id is not None:
            return self.article_id

        return self._find_article_in_value_or_extra_data(db_session)

    @classmethod
    def get_reading_completion_for_article(
        cls, article_id, user_id, number_of_activity_rows=2, threshold_for_read=0.9
    ):
        reading_activity = (
            cls.query.join(Article, cls.source_id == Article.source_id)
            .filter(Article.id == article_id)
            .filter(cls.user_id == user_id)
            .filter(cls.event == "SCROLL")
            .filter(cls.extra_data != "")
            .filter(cls.value != "")
            .order_by(desc(cls.id))
            .limit(number_of_activity_rows)
            .all()
        )
        article = Article.find_by_id(article_id)
        max_percentage_read = 0
        for ra_row in reading_activity:
            if max_percentage_read == 1:
                break
            if not ra_row.extra_data:
                continue
            try:
                scroll_data = json.loads(ra_row.extra_data)
                total_percentage_read = find_last_reading_percentage(scroll_data)
                if article.word_count < 200:
                    """
                    The method to estimate the reading percentage doesn't work well for
                    very small texts. For that reason, we check if the reading time, is
                    at least the same or longer than the estimated time, if so, we consider
                    it read.
                    """
                    from zeeguu.core.model.user_reading_session import (
                        UserReadingSession,
                    )
                    from zeeguu.core.util import ms_to_m, estimate_read_time

                    total_reading_time = (
                        UserReadingSession.get_total_reading_for_user_article(
                            article, ra_row.user
                        )
                    )
                    if ms_to_m(total_reading_time) >= estimate_read_time(
                        article.word_count, ceil=False
                    ):
                        max_percentage_read = 1
                        break
                else:
                    max_percentage_read = max(
                        max_percentage_read, total_percentage_read
                    )
            except json.decoder.JSONDecodeError:
                print("Failed to parse JSON data. Skipping row.")

        if max_percentage_read > threshold_for_read:
            return 1
        else:
            return max_percentage_read

    @classmethod
    def get_sources_ignored_by_user(
        cls, user, days_range=14, max_sources_to_filter=100, skips_required=2
    ):
        """
        Returns a list of source_ids that have been scrolled past until the user clicked on a source
        bellow the listed sources. We search within a maximum of 30 days and filter at most 100.

        skips_require define the number of times the user has scrolled past the source
        and clicked on an article or video below. The default is 2.
        """
        current_date = (datetime.now() + timedelta(1)).date()
        past_date = (datetime.now() - timedelta(days_range)).date()
        query = (
            cls.query.filter(cls.user_id == user.id)
            .filter(cls.event == EVENT_USER_CLICKED_ARTICLE)
            .filter(cls.time.between(str(past_date), str(current_date)))
            .order_by(cls.id.desc())
        )
        events = query.all()
        sources_skipped = []
        for e in events:
            parsed_source_list = json.loads(e.extra_data)
            sources_skipped += [
                s_id for s_id in parsed_source_list if Source.find_by_id(s_id)
            ]
        count_times_skipped = Counter(sources_skipped)
        sources_skipped_twice = [
            k for k, c in count_times_skipped.items() if c >= skips_required
        ]
        return sources_skipped_twice[:max_sources_to_filter]

    @classmethod
    def get_articles_with_reading_percentages_for_user_in_date_range(
        cls, user, days_range=7, limit=1
    ):
        """
        Returns a list of parsed scroll user events containing the last point which was "read"

        [(article_id:int, last_event_time:datetime, viewPortSettings:dict, last_percentage:float)]
        """

        current_date = (datetime.now() + timedelta(1)).date()
        past_date = (datetime.now() - timedelta(days_range)).date()
        query = (
            cls.query.join(Article, cls.source_id == Article.source_id)
            .filter(cls.user_id == user.id)
            .filter(cls.event == EVENT_USER_SCROLL)
            .filter(cls.time.between(str(past_date), str(current_date)))
            .order_by(cls.id.desc())
            .limit(50)
        )
        events = query.all()
        seen_articles = set()
        list_of_sessions = []
        for e in events:
            parsed_data = json.loads(e.extra_data)
            viewportSettings = e.value
            if (
                e.source_id is None
                or e.source_id in seen_articles
                or len(parsed_data) == 0
                or viewportSettings == ""
            ):
                continue
            article_data = Article.find_by_source_id(e.source_id)
            seen_articles.add(e.source_id)
            if article_data.language_id != user.learned_language_id:
                # Article doesn't match learned language
                continue

            # date_ago = (datetime.now() - e.time)
            # seconds_ago = date_ago.seconds
            last_percentage = find_last_reading_percentage(parsed_data)
            list_of_sessions.append(
                (article_data.id, e.time, json.loads(viewportSettings), last_percentage)
            )
            if len(list_of_sessions) >= limit:
                break
        return list_of_sessions

    @classmethod
    def create_from_post_data(cls, session, data, user):
        _time = data.get("time", None)
        time = None
        if _time:
            time = datetime.strptime(_time, JSON_TIME_FORMAT)

        event = data.get("event", "")
        value = data.get("value", "")
        extra_data = data.get("extra_data", "")
        source_id = data.get("source_id", "")

        article_id = None
        if data.get("article_id", None):
            article_id = int(data["article_id"])

        # This is for compatibility with some old API calls from the Web which used to pass only the articleID
        # Even more: in some of the pages we actually only have the articleId so it's easier to look it up here
        # rather than modify all the frontent
        if article_id and source_id == "":
            source_id = Article.find_by_id(article_id).source_id

        if source_id == "":
            source_id = None

        log(
            f"{event} value[:42]: {value[:42]} extra_data[:42]: {extra_data[:42]} source_id: {source_id}"
        )

        new_entry = UserActivityData.find_or_create(
            session, user, time, event, value, extra_data, source_id
        )

        session.add(new_entry)
        session.commit()

    @classmethod
    def get_last_activity_timestamp(cls, user_id):
        query = cls.query.filter(cls.user_id == user_id)
        query = query.order_by(cls.id.desc()).limit(1)

        last_event = query.first()
        if last_event:
            return last_event.time

        return None

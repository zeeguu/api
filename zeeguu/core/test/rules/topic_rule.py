import random

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.exc import NoResultFound, ObjectDeletedError

from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.model.topic import Topic


class TopicRule(BaseRule):
    """A Testing Rule class for model class zeeguu.core.model.Topics

    Has all supported languages as properties. Languages are created and
    saved to the database if they don't yet exist in the database.
    """

    topics = {
        1: "Sports",
        2: "Culture & Art",
        3: "Technology & Science",
        4: "Travel & Tourism",
        5: "Health & Society",
        6: "Business",
        7: "Politics",
        8: "Satire",
    }

    @classmethod
    def get_or_create_topic(cls, topic_id):
        topic = Topic.find_by_id(topic_id)
        if topic:
            return topic
        else:
            return TopicRule.__create_new_topic(topic_id)

    @classmethod
    def __create_new_topic(cls, topic_id):
        topic_name = cls.topics.get(topic_id)

        if topic_name is None:
            raise KeyError

        topic = Topic(topic_name)

        cls.save(topic)

        return topic

    @property
    def random(self):
        random_id, __ = random.choice(list(self.topics.items()))
        return self.get_or_create_language(random_id)

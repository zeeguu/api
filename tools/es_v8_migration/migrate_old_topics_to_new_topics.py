#!/usr/bin/env python

""" 
    Script to ensure that users have their corresponding topics in the New Topic
    mapping. 
"""

import zeeguu.core
from zeeguu.api.app import create_app
from zeeguu.core.model import TopicSubscription, TopicSubscription, Topic
from tqdm import tqdm

app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session

COMMIT_STEP = 100  # Commit after 100 updates.
VERBOSE = False  # Print every update.

OLD_TOPIC_TO_NEW_TOPIC_MAP = {
    10: 1,  # Sport -> Sports
    11: 5,  # Health -> Health & Society
    12: 3,  # Technology -> Technology & Science
    13: 7,  # Politics -> Politics
    14: 3,  # Science -> Technology & Science
    15: 2,  # Culture -> Culture & Art
    16: 4,  # Travel -> Travel & Tourism
    # 17 Food was skipped, no exact match
    18: 6,  # Business -> Business
    19: 8,  # Satire -> Satire,
    20: 2,  # Music -> Culture & Art
    21: 5,  # Social Sciences -> Health & Society
    # 22 World was skipped
    # 23 Internet was skipped
    24: 3,  # Knowledge -> Technology & Science
}


# languages = Language.available_languages()
print("Getting all current topics (old) subscriptions for users: ")
current_topics = db_session.query(TopicSubscription).all()

for i, topic_sub in tqdm(enumerate(current_topics), total=len(current_topics)):
    user = topic_sub.user
    old_topic = topic_sub.topic
    new_topic_id = OLD_TOPIC_TO_NEW_TOPIC_MAP.get(old_topic.id, None)
    if new_topic_id:
        new_topic = Topic.find_by_id(new_topic_id)
        new_user_sub = TopicSubscription.find_or_create(db_session, user, new_topic)
        if VERBOSE:
            print(
                f"User {user.id}, was subscribed to '{old_topic.title}' and now is subscribed to: '{new_topic.title}'"
            )
    if i % COMMIT_STEP == 0:
        if VERBOSE:
            print("Commiting...")
        db_session.commit()
db_session.commit()
if VERBOSE:
    print("End updating users...")

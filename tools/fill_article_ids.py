#
#    Script that loops through all the exeuser_activity_data actions in the database
#    and computes the article_id for each entry.
#
#    It skips those entries on which the has_article_id is not NULL
#    this means that it can be interruped and restarted if needed
#    
#    Normally this has to be used on zeeguu_2018-08-14.sql and then not needed anymore

import json

import zeeguu_core
from zeeguu_core.model.user_activitiy_data import UserActivityData
from zeeguu_core.model.user_reading_session import *

db_session = zeeguu_core.db.session


def _fill_in_article_id(self, session):
    self.has_article_id = False

    article_id = self._find_article_in_value_or_extra_data(session)

    if article_id:
        self.article_id = article_id
        self.has_article_id = True

        if self.value.startswith('http'):
            self.value = ''

        if self.event in [UMR_USER_FEEDBACK_ACTION, UMR_UNFOLLOW_FEED]:
            self.value = self.extra_data

        self.extra_data = ''

    session.add(self)


previous_action = {}  # tracks the previous action of a given user; key is user

commit_batch_size = 500  # committing is slow; better don't do it for every object

all_data = UserActivityData.query.all()
data = [each for each in all_data if each.id > 0]

processed_count = 0
for user_action in data:
    processed_count += 1

    if user_action.has_article_id is None:

        print(f"{processed_count} : {user_action.id} : {user_action.user.name} : {user_action.event}".encode('utf-8'))

        try:

            _fill_in_article_id(user_action, db_session)

        except Exception as e:
            # exceptions happen when an article can't be
            # created
            # in such a case, there's no reason to continue
            # trying to fill in the data from the previous
            # event... since it means that this article would
            # have existed already... thus we just let the
            # event be the way it is in the DB and move to the
            # next... also, we clear the cache of previous
            # actions. otherwise we could have the situation
            # in which an open fails but the next event type
            # w/o URL info will set the url of the previously
            # open event. not nice!
            print(e)
            import traceback

            print(traceback.format_exc())
            previous_action[user_action.user] = None
            continue

        # if we got here, it means that we have no URL info in our
        # but if the previous user action has one, and it's not a closing
        # we can safely assume that it's the same here!
        if not user_action.has_article_id and (
                user_action.event in INTERACTION_ACTIONS or user_action.event == UMR_ARTICLE_LOST_FOCUS_ACTION):

            previous_action_of_this_user = previous_action.get(user_action.user, None)

            if previous_action_of_this_user:
                if previous_action_of_this_user.event not in CLOSING_ACTIONS:
                    if previous_action_of_this_user.has_article_id:
                        user_action.has_article_id = previous_action_of_this_user.has_article_id
                        user_action.article_id = previous_action_of_this_user.article_id
                        user_action.extra_data = ''
                        if user_action.value.startswith('http'):
                            user_action.value = ''
                        db_session.add(user_action)

                        print(f"added same article_info as previous {previous_action_of_this_user.id}")

        if user_action.has_article_id:
            print(user_action.article.url.as_string() + "\n")
            previous_action[user_action.user] = user_action

        if processed_count % commit_batch_size == 0:
            db_session.commit()

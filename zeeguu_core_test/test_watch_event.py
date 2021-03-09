from datetime import datetime

from zeeguu_core_test.model_test_mixin import ModelTestMixIn
from zeeguu_core_test.rules.user_rule import UserRule
from zeeguu_core_test.rules.watch_event_type_rule import WatchEventTypeRule
from zeeguu_core_test.rules.watch_interaction_event_rule import WatchInterationEventRule
from zeeguu_core.model.smartwatch.watch_event_type import WatchEventType
from zeeguu_core.model.smartwatch.watch_interaction_event import WatchInteractionEvent
from zeeguu_core.model.user_activitiy_data import UserActivityData


class WatchEventTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()

        self.user_rule = UserRule()
        self.user = self.user_rule.user

        self.wet = WatchEventTypeRule()

    def test_new_watch_event_type(self):
        result = WatchEventType.find_by_name(self.wet.watch_event_type.name)
        assert result is not None
        assert result.name == self.wet.watch_event_type.name

    def test_watch_event(self):
        # GIVEN
        bookmark_rules = self.user_rule.add_bookmarks(1)
        bookmark = bookmark_rules[0].bookmark
        assert len(WatchInteractionEvent.events_for_bookmark(bookmark)) == 0

        # WHEN
        WatchInterationEventRule(bookmark)

        # THEN
        assert len(WatchInteractionEvent.events_for_bookmark(bookmark)) == 1

    def test_user_activity_data(self):
        uad = UserActivityData(self.user, datetime.now(), "reading", "1200", "")
        assert uad.event == "reading"

from zeeguu_core_test.rules.base_rule import BaseRule
from zeeguu_core_test.rules.watch_event_type_rule import WatchEventTypeRule
from zeeguu_core.model.smartwatch.watch_interaction_event import WatchInteractionEvent


class WatchInterationEventRule(BaseRule):
    """"A Rule testing class for the zeeguu_core.model.smartwatch.watch_interation_event model class.
    """

    def __init__(self, bookmark, watch_event_type=None):
        super().__init__()

        self.watch_interaction_event = self._create_model_object(bookmark, watch_event_type)

        self.save(self.watch_interaction_event)

    def _create_model_object(self, bookmark, watch_event_type):
        if bookmark is None:
            raise ValueError("Pass in a valid Bookmark")
        if watch_event_type is None:
            watch_event_type = WatchEventTypeRule().watch_event_type
        time = self.faker.date_time_this_month()

        watch_interaction_event = WatchInteractionEvent(watch_event_type, bookmark.id, time)

        if self._exists_in_db(watch_interaction_event):
            return self._create_model_object()

        return watch_interaction_event

    @staticmethod
    def _exists_in_db(obj):
        return False

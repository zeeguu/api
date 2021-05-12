from zeeguu_core_test.rules.base_rule import BaseRule
from zeeguu_core.model.smartwatch.watch_event_type import WatchEventType


class WatchEventTypeRule(BaseRule):
    """A Rule testing class for the zeeguu_core.model.smartwatch.watch_event_type model class.
    """

    def __init__(self):
        super().__init__()

        self.watch_event_type = self._create_model_object()

        self.save(self.watch_event_type)

    def _create_model_object(self):
        random_name = self.faker.word()

        watch_event_type = WatchEventType(random_name)

        if self._exists_in_db(watch_event_type):
            return self._create_model_object()

        return watch_event_type

    @staticmethod
    def _exists_in_db(obj):
        return False

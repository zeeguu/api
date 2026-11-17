import threading
import time
from unittest import TestCase

from zeeguu.core.model import db
from zeeguu.core.model.domain_name import DomainName
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.util.parallel import process_in_parallel


class ProcessInParallelTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.domains = []
        for i in range(10):
            domain = DomainName.find_or_create(db.session, f"https://site{i}.com/x")
            db.session.commit()
            self.domains.append(domain)
        # Newest first, like the backfill: the opposite of the database order.
        self.ids = sorted((d.id for d in self.domains), reverse=True)

    def _prepare(self, domain):
        return {"id": domain.id, "name": domain.domain_name}

    def test_results_come_back_in_the_order_of_ids(self):
        def work(data):
            # The first jobs take longest, so they finish last.
            time.sleep(0.05 if data["id"] == self.ids[0] else 0)
            return data["name"]

        results = list(
            process_in_parallel(DomainName, self.ids, self._prepare, work, workers=3)
        )

        assert [data["id"] for data, _, _ in results] == self.ids

    def test_work_runs_off_the_main_thread(self):
        main = threading.current_thread()

        results = process_in_parallel(
            DomainName,
            self.ids,
            self._prepare,
            lambda data: threading.current_thread() is main,
            workers=3,
        )

        assert not any(on_main for _, on_main, _ in results)

    def test_errors_come_back_as_values(self):
        failing_prepare_id, failing_work_id, skipped_id = self.ids[:3]

        def prepare(domain):
            if domain.id == failing_prepare_id:
                raise ValueError("prepare failed")
            if domain.id == skipped_id:
                return None
            return self._prepare(domain)

        def work(data):
            if data["id"] == failing_work_id:
                raise ValueError("work failed")
            return data["name"].upper()

        results = list(
            process_in_parallel(DomainName, self.ids, prepare, work, workers=2)
        )
        by_id = {data["id"]: (result, error) for data, result, error in results}

        assert skipped_id not in by_id
        assert str(by_id[failing_prepare_id][1]) == "prepare failed"
        assert str(by_id[failing_work_id][1]) == "work failed"
        for row_id in self.ids[3:]:
            result, error = by_id[row_id]
            assert error is None and result.startswith("HTTPS://")

    def test_only_the_chunks_rows_leave_the_session(self):
        # An object the caller holds, but not one of the processed rows.
        other = DomainName.find_or_create(db.session, "https://other.com/x")
        db.session.commit()

        list(
            process_in_parallel(
                DomainName, self.ids, self._prepare, lambda d: d, workers=1
            )
        )

        assert other in db.session

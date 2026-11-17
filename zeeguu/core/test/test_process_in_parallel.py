from unittest import TestCase

from zeeguu.core.model import db
from zeeguu.core.model.domain_name import DomainName
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.util.parallel import process_in_parallel


class ProcessInParallelTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.ids = []
        for i in range(10):
            domain = DomainName.find_or_create(db.session, f"https://site{i}.com/x")
            db.session.commit()
            self.ids.append(domain.id)

    def test_results_come_back_in_order_with_errors_as_values(self):
        def prepare(domain):
            if domain.domain_name == "https://site3.com":
                return None  # skipped
            return {"id": domain.id, "name": domain.domain_name}

        def work(data):
            if data["name"] == "https://site5.com":
                raise ValueError("boom")
            return data["name"].upper()

        # workers=1 -> chunks of 4, so this also crosses chunk boundaries
        results = list(process_in_parallel(DomainName, self.ids, prepare, work, workers=1))

        returned_ids = [data["id"] for data, _, _ in results]
        expected_ids = [i for i in self.ids if i != self.ids[3]]
        assert sorted(returned_ids) == sorted(expected_ids)

        for data, result, error in results:
            if data["name"] == "https://site5.com":
                assert result is None and isinstance(error, ValueError)
            else:
                assert error is None and result == data["name"].upper()

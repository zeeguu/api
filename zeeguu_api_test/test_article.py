# coding=utf-8

from unittest import TestCase

from zeeguu_core_test.test_data.mocking_the_web import url_spiegel_venezuela
from zeeguu_api_test.api_test_mixin import APITestMixin
import urllib.parse


class MetaTests(APITestMixin, TestCase):

    def setUp(self):
        super(MetaTests, self).setUp()

    def test_routes_should_not_end_with_slash(self):

        exceptions = ["/", "/dashboard/"]

        for rule in self.app.application.url_map.iter_rules():
            rule_name = rule.rule

            if rule_name not in exceptions:
                if rule_name[-1] == "/":
                    print("\nOops! Rules should not end in /. \nOffending rule: " + rule.rule)
                    assert (False)

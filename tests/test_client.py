from __future__ import annotations

import unittest

from barker_spider.client import BarkerClientError, extract_campaign_list


class ClientPayloadTest(unittest.TestCase):
    def test_extracts_top_level_data_list(self) -> None:
        payload = {"data": [{"pool_uid": "pool-1"}], "total": 1}

        self.assertEqual(extract_campaign_list(payload), [{"pool_uid": "pool-1"}])

    def test_extracts_nested_data_list(self) -> None:
        payload = {"data": {"list": [{"pool_uid": "pool-1"}], "total": 1}}

        self.assertEqual(extract_campaign_list(payload), [{"pool_uid": "pool-1"}])

    def test_extracts_top_level_list(self) -> None:
        payload = [{"pool_uid": "pool-1"}]

        self.assertEqual(extract_campaign_list(payload), [{"pool_uid": "pool-1"}])

    def test_error_includes_payload_context(self) -> None:
        payload = {"code": 401, "message": "invalid api key"}

        with self.assertRaisesRegex(BarkerClientError, "invalid api key"):
            extract_campaign_list(payload)


if __name__ == "__main__":
    unittest.main()

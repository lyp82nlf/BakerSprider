from __future__ import annotations

import unittest

from barker_spider.raw_view import format_raw_campaign_table


class RawViewTest(unittest.TestCase):
    def test_formats_raw_key_fields(self) -> None:
        content = format_raw_campaign_table(
            [
                {
                    "protocol_uid": "binance",
                    "campaign_name": "Lorenzo USD1",
                    "asset_symbol": "USD1",
                    "end_date": "2026-06-18T23:59:59.000Z",
                    "campaign_apy": "0.1098",
                }
            ]
        )

        self.assertIn("protocol_uid", content)
        self.assertIn("binance", content)
        self.assertIn("Lorenzo USD1", content)
        self.assertIn("USD1", content)
        self.assertIn("0.1098", content)
        self.assertIn("10.98%", content)


if __name__ == "__main__":
    unittest.main()

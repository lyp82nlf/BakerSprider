from __future__ import annotations

import unittest

from barker_spider.models import Campaign
from barker_spider.printer import format_campaign_table


class PrinterTest(unittest.TestCase):
    def test_formats_campaign_table(self) -> None:
        content = format_campaign_table(
            [
                Campaign(
                    uid="pool-1",
                    protocol_name="Binance",
                    campaign_name="Lorenzo USD1",
                    asset_symbol="USD1",
                    end_date="2026-06-19 07:59",
                    apy=10.98,
                    is_active=True,
                    pool_status="active",
                )
            ]
        )

        self.assertIn("| 交易所 | 活动 | 代币 | 到期时间 | 实时年化 |", content)
        self.assertIn("| Binance | Lorenzo USD1 | USD1 | 2026-06-19 07:59 | 10.98% |", content)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from barker_spider.models import Campaign, CampaignEvent, EventType
from barker_spider.notifier import format_events_markdown


class NotifierTest(unittest.TestCase):
    def test_message_contains_key_fields(self) -> None:
        campaign = Campaign(
            uid="pool-1",
            protocol_name="Binance",
            campaign_name="Lorenzo USD1",
            asset_symbol="USD1",
            end_date="2026-06-19 07:59",
            apy=10.98,
            is_active=True,
            pool_status="active",
        )
        content = format_events_markdown([CampaignEvent(EventType.NEW, campaign)])

        self.assertIn("Binance", content)
        self.assertIn("Lorenzo USD1", content)
        self.assertIn("USD1", content)
        self.assertIn("2026-06-19 07:59", content)
        self.assertIn("10.98%", content)


if __name__ == "__main__":
    unittest.main()

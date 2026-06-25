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

    def test_rate_increase_highlights_current_rate_and_delta(self) -> None:
        previous = Campaign(
            uid="pool-1",
            protocol_name="Binance",
            campaign_name="Native USDC",
            asset_symbol="USDC",
            end_date="2026-08-07 08:00",
            apy=13.54,
            is_active=True,
            pool_status="active",
        )
        current = Campaign(
            uid="pool-1",
            protocol_name="Binance",
            campaign_name="Native USDC",
            asset_symbol="USDC",
            end_date="2026-08-07 08:00",
            apy=15.19,
            is_active=True,
            pool_status="active",
        )

        content = format_events_markdown([CampaignEvent(EventType.RATE_CHANGED, current, previous)])

        self.assertIn('<font color="warning">15.19%</font>', content)
        self.assertIn('<font color="warning">+1.65pct</font>', content)

    def test_rate_decrease_uses_info_color(self) -> None:
        previous = Campaign(
            uid="pool-1",
            protocol_name="Binance",
            campaign_name="Native USDC",
            asset_symbol="USDC",
            end_date="2026-08-07 08:00",
            apy=15.19,
            is_active=True,
            pool_status="active",
        )
        current = Campaign(
            uid="pool-1",
            protocol_name="Binance",
            campaign_name="Native USDC",
            asset_symbol="USDC",
            end_date="2026-08-07 08:00",
            apy=13.54,
            is_active=True,
            pool_status="active",
        )

        content = format_events_markdown([CampaignEvent(EventType.RATE_CHANGED, current, previous)])

        self.assertIn('<font color="info">13.54%</font>', content)
        self.assertIn('<font color="info">-1.65pct</font>', content)


if __name__ == "__main__":
    unittest.main()

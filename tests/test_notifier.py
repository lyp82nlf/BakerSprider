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
        self.assertIn('<font color="warning">10.98%</font>', content)

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

        self.assertIn('<font color="warning">13.54%</font>', content)
        self.assertIn('<font color="warning">15.19%</font>', content)
        self.assertIn('<font color="warning">↑1.65pct</font>', content)
        self.assertIn("到期：2026-08-07 08:00", content)

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

        self.assertIn('<font color="info">15.19%</font>', content)
        self.assertIn('<font color="info">13.54%</font>', content)
        self.assertIn('<font color="info">↓1.65pct</font>', content)

    def test_merges_rate_and_end_date_changes_for_same_campaign(self) -> None:
        previous = Campaign(
            uid="pool-1",
            protocol_name="Binance",
            campaign_name="JustLend USDD",
            asset_symbol="USDD",
            end_date="2026-08-05 07:59",
            apy=7.88,
            is_active=True,
            pool_status="active",
        )
        current = Campaign(
            uid="pool-1",
            protocol_name="Binance",
            campaign_name="JustLend USDD",
            asset_symbol="USDD",
            end_date="2026-09-05 07:59",
            apy=6.22,
            is_active=True,
            pool_status="active",
        )

        content = format_events_markdown(
            [
                CampaignEvent(EventType.RATE_CHANGED, current, previous),
                CampaignEvent(EventType.END_DATE_CHANGED, current, previous),
            ]
        )

        self.assertEqual(content.count("Binance｜JustLend USDD"), 1)
        self.assertIn("APY：", content)
        self.assertIn("↓1.66pct", content)
        self.assertIn("到期：2026-08-05 07:59 → 2026-09-05 07:59", content)

    def test_single_event_message_contains_only_changed_campaign(self) -> None:
        previous = Campaign(
            uid="changed",
            protocol_name="Binance",
            campaign_name="RLUSD",
            asset_symbol="RLUSD",
            end_date="2026-08-14 08:00",
            apy=8.46,
            is_active=True,
            pool_status="active",
        )
        current = Campaign(
            uid="changed",
            protocol_name="Binance",
            campaign_name="RLUSD",
            asset_symbol="RLUSD",
            end_date="2026-08-14 08:00",
            apy=11.95,
            is_active=True,
            pool_status="active",
        )

        content = format_events_markdown([CampaignEvent(EventType.RATE_CHANGED, current, previous)])

        self.assertIn("### Barker 理财变动", content)
        self.assertEqual(content.count("**Binance｜RLUSD**"), 1)
        self.assertNotIn("新增理财", content)


if __name__ == "__main__":
    unittest.main()

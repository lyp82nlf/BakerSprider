from __future__ import annotations

import unittest

from barker_spider.normalizer import normalize_campaigns


class NormalizerTest(unittest.TestCase):
    def test_maps_api_fields_to_campaign(self) -> None:
        campaigns = normalize_campaigns(
            [
                {
                    "pool_uid": "pool-1",
                    "protocol_uid": "binance",
                    "campaign_name": "Lorenzo USD1",
                    "asset_symbol": "USD1",
                    "end_date": "2026-06-18T23:59:59.000Z",
                    "campaign_apy": "0.1098",
                    "is_active": 1,
                    "pool_status": "active",
                }
            ]
        )

        self.assertEqual(len(campaigns), 1)
        campaign = campaigns[0]
        self.assertEqual(campaign.uid, "pool-1")
        self.assertEqual(campaign.protocol_name, "Binance")
        self.assertEqual(campaign.campaign_name, "Lorenzo USD1")
        self.assertEqual(campaign.asset_symbol, "USD1")
        self.assertEqual(campaign.end_date, "2026-06-19 07:59")
        self.assertAlmostEqual(campaign.apy, 10.98)

    def test_filters_inactive_campaigns(self) -> None:
        campaigns = normalize_campaigns(
            [
                {"pool_uid": "active", "campaign_name": "A", "asset_symbol": "USDT", "is_active": 1},
                {"pool_uid": "inactive", "campaign_name": "B", "asset_symbol": "USDT", "is_active": 0},
            ],
            only_active=True,
        )

        self.assertEqual([campaign.uid for campaign in campaigns], ["active"])

    def test_keeps_already_displayed_end_date(self) -> None:
        campaigns = normalize_campaigns(
            [
                {
                    "pool_uid": "pool-1",
                    "protocol_uid": "binance",
                    "campaign_name": "U",
                    "asset_symbol": "U",
                    "end_date": "2026-06-19 07:59",
                    "campaign_apy": "0.08",
                    "is_active": 1,
                }
            ]
        )

        self.assertEqual(campaigns[0].end_date, "2026-06-19 07:59")


if __name__ == "__main__":
    unittest.main()

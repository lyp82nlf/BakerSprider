from __future__ import annotations

from datetime import datetime
import unittest

from barker_spider.daily_report import (
    LOCAL_TZ,
    build_daily_report,
    format_daily_report_markdown,
    should_send_daily_report,
)
from barker_spider.models import Campaign


def campaign(uid: str, apy: float, name: str = "U") -> Campaign:
    return Campaign(
        uid=uid,
        protocol_name="Binance",
        campaign_name=name,
        asset_symbol="USDT",
        end_date="2026-06-18 08:00",
        apy=apy,
        is_active=True,
        pool_status="active",
    )


class DailyReportTest(unittest.TestCase):
    def test_should_send_once_after_report_hour(self) -> None:
        now = datetime(2026, 6, 5, 10, 0, tzinfo=LOCAL_TZ)

        self.assertTrue(should_send_daily_report(now, 10, ""))
        self.assertFalse(should_send_daily_report(now, 10, "2026-06-05"))

    def test_does_not_send_before_report_hour(self) -> None:
        now = datetime(2026, 6, 5, 9, 59, tzinfo=LOCAL_TZ)

        self.assertFalse(should_send_daily_report(now, 10, ""))

    def test_builds_yesterday_rate_moves_and_current_high_apy(self) -> None:
        now = datetime(2026, 6, 5, 10, 0, tzinfo=LOCAL_TZ)
        snapshots = [
            {
                "timestamp": "2026-06-04T09:00:00+08:00",
                "campaigns": [campaign("rise", 8.0).to_dict(), campaign("flat", 7.0).to_dict()],
            },
            {
                "timestamp": "2026-06-04T23:00:00+08:00",
                "campaigns": [campaign("rise", 10.0).to_dict(), campaign("flat", 8.0).to_dict()],
            },
            {
                "timestamp": "2026-06-03T23:00:00+08:00",
                "campaigns": [campaign("old", 30.0).to_dict()],
            },
        ]

        report = build_daily_report(
            snapshots=snapshots,
            current_campaigns=[campaign("rise", 10.0), campaign("high", 8.01, "High")],
            now=now,
            change_threshold_points=2.0,
            high_apy_threshold=8.0,
        )

        self.assertEqual(report.report_date.isoformat(), "2026-06-04")
        self.assertEqual([move.campaign.uid for move in report.rate_moves], ["rise"])
        self.assertEqual([item.uid for item in report.high_apy_campaigns], ["rise", "high"])

    def test_formats_daily_report(self) -> None:
        now = datetime(2026, 6, 5, 10, 0, tzinfo=LOCAL_TZ)
        report = build_daily_report(
            snapshots=[
                {"timestamp": "2026-06-04T09:00:00+08:00", "campaigns": [campaign("rise", 8.0).to_dict()]},
                {"timestamp": "2026-06-04T23:00:00+08:00", "campaigns": [campaign("rise", 10.0).to_dict()]},
            ],
            current_campaigns=[campaign("rise", 10.0)],
            now=now,
            change_threshold_points=2.0,
            high_apy_threshold=8.0,
        )

        content = format_daily_report_markdown(report, 2.0, 8.0)

        self.assertIn("Barker 理财日报", content)
        self.assertIn("8.00% -> 10.00%", content)
        self.assertIn("当前利率超过 8.00%", content)


if __name__ == "__main__":
    unittest.main()

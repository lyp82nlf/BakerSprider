from __future__ import annotations

import unittest

from barker_spider.models import Campaign, EventType
from barker_spider.monitor import detect_events, run_comparison


def campaign(uid: str, apy: float = 8.0, end_date: str = "2026-06-18") -> Campaign:
    return Campaign(
        uid=uid,
        protocol_name="Binance",
        campaign_name="U",
        asset_symbol="USDT",
        end_date=end_date,
        apy=apy,
        is_active=True,
        pool_status="active",
    )


class MonitorTest(unittest.TestCase):
    def test_first_run_creates_baseline_without_events(self) -> None:
        events = run_comparison({}, [campaign("new")], rate_threshold_points=1.0, has_baseline=False)
        self.assertEqual(events, [])

    def test_detects_new_campaign(self) -> None:
        events = detect_events({}, [campaign("new")], rate_threshold_points=1.0)
        self.assertEqual([event.event_type for event in events], [EventType.NEW])

    def test_rate_change_threshold_is_absolute_points(self) -> None:
        previous = {"same": campaign("same", apy=8.0)}

        below = detect_events(previous, [campaign("same", apy=8.99)], rate_threshold_points=1.0)
        at_threshold = detect_events(previous, [campaign("same", apy=9.0)], rate_threshold_points=1.0)

        self.assertEqual(below, [])
        self.assertEqual([event.event_type for event in at_threshold], [EventType.RATE_CHANGED])

    def test_detects_end_date_change(self) -> None:
        previous = {"same": campaign("same", end_date="2026-06-18")}
        events = detect_events(previous, [campaign("same", end_date="2026-06-19")], rate_threshold_points=1.0)
        self.assertEqual([event.event_type for event in events], [EventType.END_DATE_CHANGED])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from barker_spider.models import Campaign, EventType
from barker_spider.monitor import advance_monitor_state, detect_events, run_comparison
from barker_spider.state import MonitorState


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


class StableMonitorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)

    def transition(
        self,
        state: MonitorState,
        current: list[Campaign],
        offset_minutes: int = 0,
        source_updated_at: str = "",
        source_fingerprint: str = "",
    ):
        return advance_monitor_state(
            state=state,
            current=current,
            rate_threshold_points=1.0,
            observed_at=self.now + timedelta(minutes=offset_minutes),
            source_updated_at=source_updated_at,
            source_fingerprint=source_fingerprint,
            has_baseline=True,
        )

    def stable_state(self, item: Campaign | None = None) -> MonitorState:
        items = {item.uid: item} if item else {}
        return MonitorState(latest=dict(items), baseline=dict(items))

    def test_new_campaign_requires_two_consecutive_observations(self) -> None:
        first = self.transition(self.stable_state(), [campaign("new")])
        second = self.transition(first.state, [campaign("new")], offset_minutes=5)
        third = self.transition(second.state, [campaign("new")], offset_minutes=10)

        self.assertEqual(first.events, [])
        self.assertEqual([event.event_type for event in second.events], [EventType.NEW])
        self.assertEqual(third.events, [])

    def test_unconfirmed_new_campaign_is_cancelled_when_missing(self) -> None:
        first = self.transition(self.stable_state(), [campaign("new")])
        missing = self.transition(first.state, [], offset_minutes=5)
        reappeared = self.transition(missing.state, [campaign("new")], offset_minutes=10)

        self.assertEqual(missing.state.pending_new, {})
        self.assertEqual(reappeared.events, [])
        self.assertEqual(reappeared.state.pending_new["new"][1], 1)

    def test_stable_campaign_missing_then_reappearing_is_not_new(self) -> None:
        original = campaign("same")
        missing = self.transition(self.stable_state(original), [])
        reappeared = self.transition(missing.state, [original], offset_minutes=5)

        self.assertEqual(missing.events, [])
        self.assertEqual(reappeared.events, [])
        self.assertIn("same", reappeared.state.baseline)

    def test_one_poll_rate_spike_is_cancelled(self) -> None:
        original = campaign("same", apy=8.0)
        spike = self.transition(self.stable_state(original), [campaign("same", apy=12.0)])
        recovered = self.transition(spike.state, [original], offset_minutes=5)

        self.assertEqual(spike.events, [])
        self.assertEqual(recovered.events, [])
        self.assertEqual(recovered.state.pending_rates, {})

    def test_rate_change_is_confirmed_on_second_same_direction_observation(self) -> None:
        original = campaign("same", apy=8.0)
        first = self.transition(self.stable_state(original), [campaign("same", apy=10.0)])
        second = self.transition(first.state, [campaign("same", apy=10.2)], offset_minutes=5)

        self.assertEqual(first.events, [])
        self.assertEqual([event.event_type for event in second.events], [EventType.RATE_CHANGED])
        self.assertEqual(second.events[0].previous.apy, 8.0)
        self.assertEqual(second.events[0].current.apy, 10.2)
        self.assertEqual(second.state.baseline["same"].apy, 10.2)

    def test_alternating_rate_values_do_not_notify(self) -> None:
        original = campaign("same", apy=8.46)
        state = self.stable_state(original)
        all_events = []
        for index, apy in enumerate([11.95, 8.46, 11.95, 8.46]):
            transition = self.transition(state, [campaign("same", apy=apy)], offset_minutes=index * 5)
            all_events.extend(transition.events)
            state = transition.state

        self.assertEqual(all_events, [])

    def test_end_date_change_requires_same_value_twice(self) -> None:
        original = campaign("same", end_date="长期")
        first = self.transition(self.stable_state(original), [campaign("same", end_date="2026-08-17")])
        second = self.transition(
            first.state,
            [campaign("same", end_date="2026-08-17")],
            offset_minutes=5,
        )

        self.assertEqual(first.events, [])
        self.assertEqual([event.event_type for event in second.events], [EventType.END_DATE_CHANGED])

    def test_alternating_end_dates_do_not_notify(self) -> None:
        original = campaign("same", end_date="长期")
        state = self.stable_state(original)
        all_events = []
        for index, end_date in enumerate(["2026-08-17", "长期", "2026-08-17", "长期"]):
            transition = self.transition(
                state,
                [campaign("same", end_date=end_date)],
                offset_minutes=index * 5,
            )
            all_events.extend(transition.events)
            state = transition.state

        self.assertEqual(all_events, [])

    def test_alternating_partial_batches_do_not_create_mass_events(self) -> None:
        batch_a = campaign("batch-a", apy=10.0, end_date="长期")
        batch_b = campaign("batch-b", apy=9.0, end_date="长期")
        common = campaign("common", apy=8.46, end_date="2026-08-17")
        baseline = {
            item.uid: item
            for item in [batch_a, batch_b, common]
        }
        state = MonitorState(latest=dict(baseline), baseline=dict(baseline))

        first = self.transition(
            state,
            [batch_a, campaign("common", apy=11.95, end_date="长期")],
        )
        second = self.transition(
            first.state,
            [batch_b, common],
            offset_minutes=5,
        )

        self.assertEqual(first.events, [])
        self.assertEqual(second.events, [])
        self.assertEqual(set(second.state.baseline), {"batch-a", "batch-b", "common"})

    def test_rate_and_end_date_can_confirm_together(self) -> None:
        original = campaign("same", apy=8.0, end_date="长期")
        changed = campaign("same", apy=10.0, end_date="2026-08-17")
        first = self.transition(self.stable_state(original), [changed])
        second = self.transition(first.state, [changed], offset_minutes=5)

        self.assertEqual(
            [event.event_type for event in second.events],
            [EventType.RATE_CHANGED, EventType.END_DATE_CHANGED],
        )

    def test_older_source_version_is_rejected(self) -> None:
        state = self.stable_state(campaign("same"))
        state.source_updated_at = "2026-08-06T02:00:00+00:00"
        state.source_fingerprint = "newer"

        result = self.transition(
            state,
            [campaign("same", apy=12.0)],
            source_updated_at="2026-08-06T01:00:00+00:00",
            source_fingerprint="older",
        )

        self.assertFalse(result.accepted)
        self.assertIn("stale source version", result.reason)

    def test_conflicting_payload_for_same_source_version_is_rejected(self) -> None:
        state = self.stable_state(campaign("same"))
        state.source_updated_at = "2026-08-06T02:00:00+00:00"
        state.source_fingerprint = "first"

        result = self.transition(
            state,
            [campaign("same", apy=12.0)],
            source_updated_at="2026-08-06T02:00:00+00:00",
            source_fingerprint="different",
        )

        self.assertFalse(result.accepted)
        self.assertIn("conflicting payload", result.reason)


if __name__ == "__main__":
    unittest.main()

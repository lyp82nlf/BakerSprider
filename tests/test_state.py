from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from barker_spider.models import Campaign
from barker_spider.state import CampaignHistory, CampaignState, MonitorState


def campaign(uid: str, apy: float = 8.0) -> Campaign:
    return Campaign(
        uid=uid,
        protocol_name="Binance",
        campaign_name="U",
        asset_symbol="U",
        end_date="长期",
        apy=apy,
        is_active=True,
        pool_status="active",
    )


class CampaignStateTest(unittest.TestCase):
    def test_legacy_snapshot_becomes_stable_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "campaigns.json"
            existing = campaign("existing")
            path.write_text(
                json.dumps({"campaigns": {existing.uid: existing.to_dict()}}),
                encoding="utf-8",
            )

            state = CampaignState(path).load_monitor_state()

            self.assertEqual(state.latest, {"existing": existing})
            self.assertEqual(state.baseline, {"existing": existing})
            self.assertEqual(state.pending_new, {})

    def test_monitor_state_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "campaigns.json"
            existing = campaign("existing")
            new = campaign("new", apy=10.0)
            expected = MonitorState(
                latest={"existing": existing},
                baseline={"existing": existing},
                pending_new={"new": (new, 1)},
                pending_rates={"existing": (1, 1)},
                pending_end_dates={"existing": ("2026-08-17", 1)},
                last_seen_at={"existing": "2026-08-06T10:00:00+00:00"},
                source_updated_at="2026-08-06T02:00:00+00:00",
                source_fingerprint="fingerprint",
            )

            store = CampaignState(path)
            store.save_monitor_state(expected)
            actual = store.load_monitor_state()

            self.assertEqual(actual.latest, expected.latest)
            self.assertEqual(actual.baseline, expected.baseline)
            self.assertEqual(actual.pending_new, expected.pending_new)
            self.assertEqual(actual.pending_rates, expected.pending_rates)
            self.assertEqual(actual.pending_end_dates, expected.pending_end_dates)
            self.assertEqual(actual.last_seen_at, expected.last_seen_at)
            self.assertEqual(actual.source_updated_at, expected.source_updated_at)
            self.assertEqual(actual.source_fingerprint, expected.source_fingerprint)

    def test_regular_save_preserves_monitor_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "campaigns.json"
            existing = campaign("existing")
            store = CampaignState(path)
            store.save_monitor_state(
                MonitorState(
                    latest={"existing": existing},
                    baseline={"existing": existing},
                    source_updated_at="2026-08-06T02:00:00+00:00",
                    source_fingerprint="fingerprint",
                )
            )

            replacement = campaign("replacement")
            store.save([replacement])
            actual = store.load_monitor_state()

            self.assertEqual(actual.latest, {"replacement": replacement})
            self.assertEqual(actual.baseline, {"existing": existing})
            self.assertEqual(actual.source_fingerprint, "fingerprint")

    def test_history_recovers_latest_version_of_every_seen_campaign(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.jsonl"
            history = CampaignHistory(path)
            history.append_snapshot("2026-08-06T09:00:00+00:00", [campaign("first"), campaign("same", 8.0)])
            history.append_snapshot("2026-08-06T09:05:00+00:00", [campaign("second"), campaign("same", 9.0)])

            latest = history.load_latest_campaigns()

            self.assertEqual(set(latest), {"first", "second", "same"})
            self.assertEqual(latest["same"].apy, 9.0)


if __name__ == "__main__":
    unittest.main()

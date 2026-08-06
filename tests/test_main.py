from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import barker_spider.__main__ as cli
from barker_spider.normalizer import normalize_campaigns
from barker_spider.notifier import WeComNotifierError
from barker_spider.state import CampaignHistory, CampaignState


def raw_campaign(apy: float, uid: str = "same") -> dict:
    return {
        "pool_uid": uid,
        "protocol_uid": "binance",
        "campaign_name": "RLUSD" if uid == "same" else uid.upper(),
        "asset_symbol": "RLUSD",
        "end_date": "2026-08-14T00:00:00.000Z",
        "campaign_apy": apy,
        "is_active": 1,
        "pool_status": "active",
    }


class FakeConfig:
    def __init__(self, directory: str) -> None:
        root = Path(directory)
        self.state_path = root / "snapshot.json"
        self.history_path = root / "history.jsonl"
        self.report_state_path = root / "report.json"
        self.only_active = True
        self.rate_threshold_points = 1.0
        self.daily_report_enabled = False
        self.wecom_webhook_url = "https://example.invalid/webhook"

    def validate_for_fetch(self) -> None:
        return None

    def validate_for_notify(self) -> None:
        return None


class FakeClient:
    def __init__(self, items: list[dict]) -> None:
        self.items = items

    def fetch_campaigns(self) -> list[dict]:
        return self.items


class RunOnceTest(unittest.TestCase):
    def test_legacy_migration_uses_history_to_avoid_false_new_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = FakeConfig(directory)
            store = CampaignState(config.state_path)
            store.save(normalize_campaigns([raw_campaign(0.08, uid="snapshot-only")]))
            CampaignHistory(config.history_path).append_snapshot(
                "2026-08-06T09:00:00+00:00",
                normalize_campaigns([raw_campaign(0.09, uid="history-only")]),
            )

            with patch.object(
                cli,
                "build_client",
                return_value=FakeClient([raw_campaign(0.09, uid="history-only")]),
            ):
                cli.run_once(config, dry_run=True)

            migrated = store.load_monitor_state()
            self.assertEqual(set(migrated.baseline), {"snapshot-only", "history-only"})
            self.assertEqual(migrated.pending_new, {})

    def test_failed_notification_does_not_commit_baseline_and_retries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = FakeConfig(directory)

            with patch.object(cli, "build_client", return_value=FakeClient([raw_campaign(0.08)])):
                cli.run_once(config, dry_run=True)

            with patch.object(cli, "build_client", return_value=FakeClient([raw_campaign(0.10)])):
                cli.run_once(config, dry_run=True)

            with (
                patch.object(cli, "build_client", return_value=FakeClient([raw_campaign(0.10)])),
                patch.object(cli.WeComNotifier, "send_markdown", side_effect=WeComNotifierError("failed")),
            ):
                with self.assertRaises(WeComNotifierError):
                    cli.run_once(config)

            after_failure = CampaignState(config.state_path).load_monitor_state()
            self.assertEqual(after_failure.baseline["same"].apy, 8.0)
            self.assertEqual(after_failure.pending_rates["same"], (1, 1))

            with (
                patch.object(cli, "build_client", return_value=FakeClient([raw_campaign(0.10)])),
                patch.object(cli.WeComNotifier, "send_markdown") as send,
            ):
                cli.run_once(config)

            self.assertEqual(send.call_count, 1)
            self.assertIn("**Binance｜RLUSD**", send.call_args.args[0])
            final_state = CampaignState(config.state_path).load_monitor_state()
            self.assertEqual(final_state.baseline["same"].apy, 10.0)


if __name__ == "__main__":
    unittest.main()

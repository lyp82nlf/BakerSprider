from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any

from .models import Campaign


class MonitorState:
    def __init__(
        self,
        latest: dict[str, Campaign] | None = None,
        baseline: dict[str, Campaign] | None = None,
        pending_new: dict[str, tuple[Campaign, int]] | None = None,
        pending_rates: dict[str, tuple[int, int]] | None = None,
        pending_end_dates: dict[str, tuple[str, int]] | None = None,
        last_seen_at: dict[str, str] | None = None,
        source_updated_at: str = "",
        source_fingerprint: str = "",
    ) -> None:
        self.latest = latest or {}
        self.baseline = baseline or {}
        self.pending_new = pending_new or {}
        self.pending_rates = pending_rates or {}
        self.pending_end_dates = pending_end_dates or {}
        self.last_seen_at = last_seen_at or {}
        self.source_updated_at = source_updated_at
        self.source_fingerprint = source_fingerprint


class CampaignState:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> dict[str, Campaign]:
        payload = self._load_payload()
        campaigns = payload.get("campaigns", {})
        if not isinstance(campaigns, dict):
            return {}

        return _load_campaign_map(campaigns)

    def load_monitor_state(self) -> MonitorState:
        payload = self._load_payload()
        latest = _load_campaign_map(payload.get("campaigns", {}))
        raw_monitor = payload.get("monitor")
        if not isinstance(raw_monitor, dict):
            return MonitorState(latest=latest, baseline=dict(latest))

        baseline = _load_campaign_map(raw_monitor.get("baseline", {}))
        pending_new = _load_pending_new(raw_monitor.get("pending_new", {}))
        pending_rates = _load_pair_map(raw_monitor.get("pending_rates", {}), "direction")
        pending_end_dates = _load_pair_map(raw_monitor.get("pending_end_dates", {}), "end_date")
        last_seen_at = raw_monitor.get("last_seen_at", {})
        if not isinstance(last_seen_at, dict):
            last_seen_at = {}

        return MonitorState(
            latest=latest,
            baseline=baseline,
            pending_new=pending_new,
            pending_rates=_load_pending_rates(pending_rates),
            pending_end_dates={uid: (str(value), count) for uid, (value, count) in pending_end_dates.items()},
            last_seen_at={str(uid): str(value) for uid, value in last_seen_at.items()},
            source_updated_at=str(raw_monitor.get("source_updated_at", "")),
            source_fingerprint=str(raw_monitor.get("source_fingerprint", "")),
        )

    def has_monitor_state(self) -> bool:
        return isinstance(self._load_payload().get("monitor"), dict)

    def save(self, campaigns: list[Campaign]) -> None:
        payload = self._load_payload()
        payload["campaigns"] = _dump_campaign_map({campaign.uid: campaign for campaign in campaigns})
        self._write_payload(payload)

    def save_monitor_state(self, state: MonitorState) -> None:
        payload = {
            "campaigns": _dump_campaign_map(state.latest),
            "monitor": {
                "baseline": _dump_campaign_map(state.baseline),
                "pending_new": {
                    uid: {"campaign": campaign.to_dict(), "observations": observations}
                    for uid, (campaign, observations) in state.pending_new.items()
                },
                "pending_rates": {
                    uid: {"direction": direction, "observations": observations}
                    for uid, (direction, observations) in state.pending_rates.items()
                },
                "pending_end_dates": {
                    uid: {"end_date": end_date, "observations": observations}
                    for uid, (end_date, observations) in state.pending_end_dates.items()
                },
                "last_seen_at": state.last_seen_at,
                "source_updated_at": state.source_updated_at,
                "source_fingerprint": state.source_fingerprint,
            },
        }
        self._write_payload(payload)

    def _load_payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as file:
                file.write(content)
                file.flush()
                temporary_path = Path(file.name)
            temporary_path.replace(self.path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()


def _load_campaign_map(value: Any) -> dict[str, Campaign]:
    if not isinstance(value, dict):
        return {}
    return {
        str(uid): Campaign.from_dict(data)
        for uid, data in value.items()
        if isinstance(data, dict)
    }


def _dump_campaign_map(campaigns: dict[str, Campaign]) -> dict[str, dict[str, Any]]:
    return {uid: campaign.to_dict() for uid, campaign in campaigns.items()}


def _load_pending_new(value: Any) -> dict[str, tuple[Campaign, int]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, tuple[Campaign, int]] = {}
    for uid, item in value.items():
        if not isinstance(item, dict) or not isinstance(item.get("campaign"), dict):
            continue
        observations = _positive_int(item.get("observations"))
        result[str(uid)] = (Campaign.from_dict(item["campaign"]), observations)
    return result


def _load_pair_map(value: Any, field: str) -> dict[str, tuple[Any, int]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, tuple[Any, int]] = {}
    for uid, item in value.items():
        if not isinstance(item, dict) or field not in item:
            continue
        result[str(uid)] = (item[field], _positive_int(item.get("observations")))
    return result


def _load_pending_rates(value: dict[str, tuple[Any, int]]) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    for uid, (direction, observations) in value.items():
        try:
            parsed_direction = int(direction)
        except (TypeError, ValueError):
            continue
        if parsed_direction not in {-1, 1}:
            continue
        result[uid] = (parsed_direction, observations)
    return result


def _positive_int(value: Any) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


class CampaignHistory:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append_snapshot(self, timestamp: str, campaigns: list[Campaign]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": timestamp,
            "campaigns": [campaign.to_dict() for campaign in campaigns],
        }
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def load_snapshots(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []

        snapshots: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                snapshots.append(payload)
        return snapshots

    def load_latest_campaigns(self) -> dict[str, Campaign]:
        latest: dict[str, Campaign] = {}
        for snapshot in self.load_snapshots():
            campaigns = snapshot.get("campaigns", [])
            if not isinstance(campaigns, list):
                continue
            for item in campaigns:
                if not isinstance(item, dict):
                    continue
                try:
                    campaign = Campaign.from_dict(item)
                except (KeyError, TypeError, ValueError):
                    continue
                latest[campaign.uid] = campaign
        return latest


class ReportState:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def last_report_date(self) -> str:
        if not self.path.exists():
            return ""
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return ""
        if not isinstance(payload, dict):
            return ""
        return str(payload.get("last_daily_report_date", ""))

    def save_last_report_date(self, report_date: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"last_daily_report_date": report_date}
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

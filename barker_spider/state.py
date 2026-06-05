from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Campaign


class CampaignState:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> dict[str, Campaign]:
        if not self.path.exists():
            return {}

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        campaigns = payload.get("campaigns", {})
        if not isinstance(campaigns, dict):
            return {}

        return {
            uid: Campaign.from_dict(data)
            for uid, data in campaigns.items()
            if isinstance(data, dict)
        }

    def save(self, campaigns: list[Campaign]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "campaigns": {
                campaign.uid: campaign.to_dict()
                for campaign in campaigns
            }
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


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

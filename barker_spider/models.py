from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .fields import display_end_date, display_protocol, normalize_apy


@dataclass(frozen=True)
class Campaign:
    uid: str
    protocol_name: str
    campaign_name: str
    asset_symbol: str
    end_date: str
    apy: float
    is_active: bool
    pool_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "protocol_name": self.protocol_name,
            "campaign_name": self.campaign_name,
            "asset_symbol": self.asset_symbol,
            "end_date": self.end_date,
            "apy": self.apy,
            "is_active": self.is_active,
            "pool_status": self.pool_status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Campaign":
        return cls(
            uid=str(data["uid"]),
            protocol_name=display_protocol(str(data.get("protocol_name", ""))),
            campaign_name=str(data.get("campaign_name", "")),
            asset_symbol=str(data.get("asset_symbol", "")),
            end_date=display_end_date(str(data.get("end_date", ""))),
            apy=normalize_apy(float(data.get("apy", 0.0))),
            is_active=bool(data.get("is_active", False)),
            pool_status=str(data.get("pool_status", "")),
        )


class EventType(str, Enum):
    NEW = "new"
    RATE_CHANGED = "rate_changed"
    END_DATE_CHANGED = "end_date_changed"


@dataclass(frozen=True)
class CampaignEvent:
    event_type: EventType
    current: Campaign
    previous: Campaign | None = None

    @property
    def sort_key(self) -> tuple[int, str]:
        order = {
            EventType.NEW: 0,
            EventType.RATE_CHANGED: 1,
            EventType.END_DATE_CHANGED: 2,
        }
        return order[self.event_type], self.current.protocol_name

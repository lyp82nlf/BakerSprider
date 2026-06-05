from __future__ import annotations

import hashlib
from typing import Any

from .fields import display_end_date, display_protocol, normalize_apy
from .models import Campaign


def normalize_campaigns(raw_items: list[dict[str, Any]], only_active: bool = True) -> list[Campaign]:
    campaigns = [campaign for item in raw_items if (campaign := normalize_campaign(item))]
    if only_active:
        campaigns = [campaign for campaign in campaigns if campaign.is_active]
    return sorted(campaigns, key=lambda campaign: (campaign.protocol_name, campaign.campaign_name, campaign.uid))


def normalize_campaign(item: dict[str, Any]) -> Campaign | None:
    uid = _first_text(item, "pool_uid")
    protocol_name = _first_text(item, "protocol_uid")
    campaign_name = _first_text(item, "campaign_name")
    asset_symbol = _first_text(item, "asset_symbol")
    end_date = display_end_date(_first_text(item, "end_date"))
    apy = normalize_apy(_first_number(item, "campaign_apy"))
    is_active = _is_active(item)
    pool_status = _first_text(item, "pool_status", "status")

    if not uid:
        uid = _fallback_uid(protocol_name, campaign_name, asset_symbol, end_date)
    if not campaign_name and not asset_symbol:
        return None

    return Campaign(
        uid=uid,
        protocol_name=display_protocol(protocol_name) or "-",
        campaign_name=campaign_name or "-",
        asset_symbol=asset_symbol or "-",
        end_date=end_date or "-",
        apy=apy,
        is_active=is_active,
        pool_status=pool_status,
    )


def _first_text(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _first_number(item: dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = item.get(key)
        if value is None or value == "":
            continue
        try:
            return float(str(value).replace("%", "").strip())
        except ValueError:
            continue
    return 0.0


def _is_active(item: dict[str, Any]) -> bool:
    value = item.get("is_active")
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "active", "yes", "y"}

    status = str(item.get("pool_status", item.get("status", ""))).strip().lower()
    if status in {"ended", "closed", "inactive", "finished"}:
        return False
    return True


def _fallback_uid(protocol_name: str, campaign_name: str, asset_symbol: str, end_date: str) -> str:
    raw = "|".join([protocol_name, campaign_name, asset_symbol, end_date])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any

from .models import Campaign, CampaignEvent, EventType
from .state import MonitorState


REQUIRED_CONFIRMATIONS = 2
STALE_CAMPAIGN_DAYS = 30


@dataclass(frozen=True)
class MonitorTransition:
    accepted: bool
    events: list[CampaignEvent]
    state: MonitorState
    reason: str = ""


def detect_events(
    previous: dict[str, Campaign],
    current: list[Campaign],
    rate_threshold_points: float,
) -> list[CampaignEvent]:
    events: list[CampaignEvent] = []

    for campaign in current:
        old = previous.get(campaign.uid)
        if old is None:
            events.append(CampaignEvent(EventType.NEW, campaign))
            continue

        if abs(campaign.apy - old.apy) >= rate_threshold_points:
            events.append(CampaignEvent(EventType.RATE_CHANGED, campaign, old))

        if _normalize_end_date(campaign.end_date) != _normalize_end_date(old.end_date):
            events.append(CampaignEvent(EventType.END_DATE_CHANGED, campaign, old))

    return sorted(events, key=lambda event: event.sort_key)


def _normalize_end_date(value: str) -> str:
    return " ".join(str(value).strip().split())


def run_comparison(
    previous: dict[str, Campaign],
    current: list[Campaign],
    rate_threshold_points: float,
    has_baseline: bool,
) -> list[CampaignEvent]:
    if not has_baseline:
        return []
    return detect_events(previous, current, rate_threshold_points)


def advance_monitor_state(
    state: MonitorState,
    current: list[Campaign],
    rate_threshold_points: float,
    observed_at: datetime,
    source_updated_at: str,
    source_fingerprint: str,
    has_baseline: bool,
) -> MonitorTransition:
    rejection_reason = _source_rejection_reason(state, source_updated_at, source_fingerprint)
    if rejection_reason:
        return MonitorTransition(False, [], state, rejection_reason)

    current_by_uid = {campaign.uid: campaign for campaign in current}
    observed_at_text = observed_at.isoformat()
    next_source_updated_at = source_updated_at or state.source_updated_at
    next_source_fingerprint = source_fingerprint if source_updated_at else state.source_fingerprint

    if not has_baseline:
        initial = MonitorState(
            latest=dict(current_by_uid),
            baseline=dict(current_by_uid),
            last_seen_at={uid: observed_at_text for uid in current_by_uid},
            source_updated_at=next_source_updated_at,
            source_fingerprint=next_source_fingerprint,
        )
        return MonitorTransition(True, [], initial)

    latest = dict(state.latest)
    latest.update(current_by_uid)
    baseline = dict(state.baseline)
    pending_rates = {
        uid: value for uid, value in state.pending_rates.items()
        if uid in baseline
    }
    pending_end_dates = {
        uid: value for uid, value in state.pending_end_dates.items()
        if uid in baseline
    }
    last_seen_at = dict(state.last_seen_at)
    for uid in baseline:
        last_seen_at.setdefault(uid, observed_at_text)
    for uid in current_by_uid:
        last_seen_at[uid] = observed_at_text

    events: list[CampaignEvent] = []
    pending_new: dict[str, tuple[Campaign, int]] = {}
    confirmed_new: set[str] = set()

    for uid, campaign in current_by_uid.items():
        if uid in baseline:
            continue
        previous_candidate = state.pending_new.get(uid)
        observations = previous_candidate[1] + 1 if previous_candidate else 1
        if observations >= REQUIRED_CONFIRMATIONS:
            baseline[uid] = campaign
            confirmed_new.add(uid)
            events.append(CampaignEvent(EventType.NEW, campaign))
        else:
            pending_new[uid] = (campaign, observations)

    for uid, campaign in current_by_uid.items():
        if uid in confirmed_new or uid not in baseline:
            continue

        previous = baseline[uid]
        next_apy = previous.apy
        next_end_date = previous.end_date
        delta = campaign.apy - previous.apy

        if abs(delta) >= rate_threshold_points:
            direction = 1 if delta > 0 else -1
            candidate = pending_rates.get(uid)
            observations = candidate[1] + 1 if candidate and candidate[0] == direction else 1
            if observations >= REQUIRED_CONFIRMATIONS:
                events.append(CampaignEvent(EventType.RATE_CHANGED, campaign, previous))
                next_apy = campaign.apy
                pending_rates.pop(uid, None)
            else:
                pending_rates[uid] = (direction, observations)
        else:
            pending_rates.pop(uid, None)

        if _normalize_end_date(campaign.end_date) != _normalize_end_date(previous.end_date):
            normalized_end_date = _normalize_end_date(campaign.end_date)
            candidate = pending_end_dates.get(uid)
            observations = candidate[1] + 1 if candidate and candidate[0] == normalized_end_date else 1
            if observations >= REQUIRED_CONFIRMATIONS:
                events.append(CampaignEvent(EventType.END_DATE_CHANGED, campaign, previous))
                next_end_date = campaign.end_date
                pending_end_dates.pop(uid, None)
            else:
                pending_end_dates[uid] = (normalized_end_date, observations)
        else:
            pending_end_dates.pop(uid, None)

        baseline[uid] = replace(
            previous,
            protocol_name=campaign.protocol_name,
            campaign_name=campaign.campaign_name,
            asset_symbol=campaign.asset_symbol,
            apy=next_apy,
            end_date=next_end_date,
            is_active=campaign.is_active,
            pool_status=campaign.pool_status,
        )

    _prune_stale_campaigns(
        observed_at,
        latest,
        baseline,
        pending_new,
        pending_rates,
        pending_end_dates,
        last_seen_at,
    )

    next_state = MonitorState(
        latest=latest,
        baseline=baseline,
        pending_new=pending_new,
        pending_rates=pending_rates,
        pending_end_dates=pending_end_dates,
        last_seen_at=last_seen_at,
        source_updated_at=next_source_updated_at,
        source_fingerprint=next_source_fingerprint,
    )
    return MonitorTransition(True, sorted(events, key=lambda event: event.sort_key), next_state)


def extract_source_updated_at(raw_items: list[dict[str, Any]]) -> str:
    timestamps = [
        parsed
        for item in raw_items
        if (parsed := _parse_datetime(str(item.get("updated_at", "")))) is not None
    ]
    if not timestamps:
        return ""
    return max(timestamps).isoformat()


def campaign_fingerprint(campaigns: list[Campaign]) -> str:
    rows = [
        [campaign.uid, round(campaign.apy, 12), campaign.end_date, campaign.is_active]
        for campaign in sorted(campaigns, key=lambda item: item.uid)
    ]
    canonical = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _source_rejection_reason(
    state: MonitorState,
    source_updated_at: str,
    source_fingerprint: str,
) -> str:
    previous_time = _parse_datetime(state.source_updated_at)
    current_time = _parse_datetime(source_updated_at)
    if previous_time is None or current_time is None:
        return ""
    if current_time < previous_time:
        return f"stale source version {source_updated_at}; latest is {state.source_updated_at}"
    if (
        current_time == previous_time
        and state.source_fingerprint
        and source_fingerprint
        and source_fingerprint != state.source_fingerprint
    ):
        return f"conflicting payload for source version {source_updated_at}"
    return ""


def _prune_stale_campaigns(
    observed_at: datetime,
    latest: dict[str, Campaign],
    baseline: dict[str, Campaign],
    pending_new: dict[str, tuple[Campaign, int]],
    pending_rates: dict[str, tuple[int, int]],
    pending_end_dates: dict[str, tuple[str, int]],
    last_seen_at: dict[str, str],
) -> None:
    cutoff = observed_at - timedelta(days=STALE_CAMPAIGN_DAYS)
    stale_uids = [
        uid for uid, value in last_seen_at.items()
        if (last_seen := _parse_datetime(value)) is not None and last_seen < cutoff
    ]
    for uid in stale_uids:
        latest.pop(uid, None)
        baseline.pop(uid, None)
        pending_new.pop(uid, None)
        pending_rates.pop(uid, None)
        pending_end_dates.pop(uid, None)
        last_seen_at.pop(uid, None)


def _parse_datetime(value: str) -> datetime | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed

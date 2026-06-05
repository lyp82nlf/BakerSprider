from __future__ import annotations

from .models import Campaign, CampaignEvent, EventType


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

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import Campaign, CampaignEvent, EventType

COLOR_UP = "warning"
COLOR_DOWN = "info"
COLOR_HIGH = "warning"


class WeComNotifierError(RuntimeError):
    pass


class WeComNotifier:
    def __init__(self, webhook_url: str, timeout_seconds: int = 15) -> None:
        self.webhook_url = webhook_url
        self.timeout_seconds = timeout_seconds

    def send_markdown(self, content: str) -> None:
        payload = json.dumps(
            {
                "msgtype": "markdown",
                "markdown": {"content": content},
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            self.webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError) as exc:
            raise WeComNotifierError(f"Failed to send WeCom notification: {exc}") from exc

        try:
            result = json.loads(body)
        except json.JSONDecodeError as exc:
            raise WeComNotifierError(f"WeCom returned non-JSON response: {body}") from exc

        if result.get("errcode") != 0:
            raise WeComNotifierError(f"WeCom returned error: {result}")


def format_events_markdown(events: list[CampaignEvent]) -> str:
    grouped = _group_events_by_campaign(events)
    event_types = {event.event_type for event in events}
    if event_types == {EventType.NEW}:
        title = "### Barker 新增理财"
    elif EventType.NEW not in event_types:
        title = "### Barker 理财变动"
    else:
        title = "### Barker 理财更新"

    lines = [title]
    for group in sorted(grouped, key=_event_group_sort_key):
        lines.append("")
        lines.extend(_format_event_group(group))

    return "\n".join(lines)


def _group_events_by_campaign(events: list[CampaignEvent]) -> list[list[CampaignEvent]]:
    grouped: dict[str, list[CampaignEvent]] = {}
    for event in events:
        grouped.setdefault(event.current.uid, []).append(event)
    return list(grouped.values())


def _event_group_sort_key(group: list[CampaignEvent]) -> tuple[int, float, str, str]:
    campaign = group[0].current
    by_type = {event.event_type: event for event in group}
    if EventType.NEW in by_type:
        return 0, -campaign.apy, campaign.protocol_name, campaign.campaign_name
    rate_event = by_type.get(EventType.RATE_CHANGED)
    if rate_event and rate_event.previous:
        return 1, -abs(campaign.apy - rate_event.previous.apy), campaign.protocol_name, campaign.campaign_name
    return 2, 0.0, campaign.protocol_name, campaign.campaign_name


def _format_event_group(group: list[CampaignEvent]) -> list[str]:
    campaign = group[0].current
    by_type = {event.event_type: event for event in group}
    lines = [f"**{campaign.protocol_name}｜{campaign.campaign_name}**"]

    if EventType.NEW in by_type:
        lines.append(
            f"代币：{campaign.asset_symbol}｜APY：{colored(format_apy(campaign), COLOR_HIGH)}"
            f"｜到期：{campaign.end_date}"
        )
        return lines

    lines.append(f"代币：{campaign.asset_symbol}")
    rate_event = by_type.get(EventType.RATE_CHANGED)
    if rate_event and rate_event.previous:
        delta = campaign.apy - rate_event.previous.apy
        color = rate_change_color(delta)
        lines.append(
            f"APY：{colored(format_apy(rate_event.previous), color)} → "
            f"{colored(format_apy(campaign), color)}（{colored(format_movement(delta), color)}）"
        )

    end_date_event = by_type.get(EventType.END_DATE_CHANGED)
    if end_date_event and end_date_event.previous:
        lines.append(f"到期：{end_date_event.previous.end_date} → {campaign.end_date}")
    elif rate_event:
        lines.append(f"到期：{campaign.end_date}")

    if end_date_event and not rate_event:
        lines.append(f"当前 APY：{colored(format_apy(campaign), COLOR_HIGH)}")

    return lines


def format_apy(campaign: Campaign) -> str:
    return f"{campaign.apy:.2f}%"


def format_percent(value: float) -> str:
    return f"{value:.2f}%"


def format_delta(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}pct"


def format_movement(value: float) -> str:
    arrow = "↑" if value >= 0 else "↓"
    return f"{arrow}{abs(value):.2f}pct"


def rate_change_color(delta: float) -> str:
    return COLOR_UP if delta >= 0 else COLOR_DOWN


def colored(text: str, color: str) -> str:
    return f'<font color="{color}">{text}</font>'

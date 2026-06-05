from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import Campaign, CampaignEvent, EventType


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
    lines = ["### Barker 理财监控提醒"]
    groups = [
        (EventType.NEW, "新增理财"),
        (EventType.RATE_CHANGED, "利率变化"),
        (EventType.END_DATE_CHANGED, "到期时间变化"),
    ]

    for event_type, title in groups:
        group_events = [event for event in events if event.event_type == event_type]
        if not group_events:
            continue
        lines.append("")
        lines.append(f"**{title}**")
        for event in group_events:
            lines.extend(_format_event_lines(event))

    return "\n".join(lines)


def _format_event_lines(event: CampaignEvent) -> list[str]:
    campaign = event.current
    if event.event_type == EventType.NEW:
        suffix = ""
    elif event.event_type == EventType.RATE_CHANGED and event.previous:
        suffix = f"；利率 {format_apy(event.previous)} -> {format_apy(campaign)}"
    elif event.event_type == EventType.END_DATE_CHANGED and event.previous:
        suffix = f"；到期 {event.previous.end_date} -> {campaign.end_date}"
    else:
        suffix = ""

    return [
        f"- {campaign.protocol_name}｜{campaign.campaign_name}",
        f"  代币：{campaign.asset_symbol}；到期：{campaign.end_date}；实时年化：{format_apy(campaign)}{suffix}",
    ]


def format_apy(campaign: Campaign) -> str:
    return f"{campaign.apy:.2f}%"

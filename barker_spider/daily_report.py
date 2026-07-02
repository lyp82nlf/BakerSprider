from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .models import Campaign
from .notifier import COLOR_HIGH, colored, format_apy, format_percent, rate_change_color

LOCAL_TZ = ZoneInfo("Asia/Shanghai")
MAX_DAILY_REPORT_ITEMS = 10


@dataclass(frozen=True)
class RateMove:
    campaign: Campaign
    start_apy: float
    end_apy: float

    @property
    def delta(self) -> float:
        return self.end_apy - self.start_apy


@dataclass(frozen=True)
class DailyReport:
    report_date: date
    rate_moves: list[RateMove]
    high_apy_campaigns: list[Campaign]


def should_send_daily_report(now: datetime, report_hour: int, last_report_date: str) -> bool:
    local_now = now.astimezone(LOCAL_TZ)
    today = local_now.date().isoformat()
    return local_now.hour >= report_hour and last_report_date != today


def build_daily_report(
    snapshots: list[dict[str, Any]],
    current_campaigns: list[Campaign],
    now: datetime,
    change_threshold_points: float,
    high_apy_threshold: float,
) -> DailyReport:
    report_date = now.astimezone(LOCAL_TZ).date() - timedelta(days=1)
    yesterday_snapshots = _snapshots_for_date(snapshots, report_date)
    rate_moves = _detect_rate_moves(yesterday_snapshots, change_threshold_points)
    high_apy_campaigns = [
        campaign for campaign in current_campaigns
        if campaign.apy > high_apy_threshold
    ]
    high_apy_campaigns.sort(key=lambda campaign: (-campaign.apy, campaign.protocol_name, campaign.campaign_name))

    return DailyReport(
        report_date=report_date,
        rate_moves=rate_moves,
        high_apy_campaigns=high_apy_campaigns,
    )


def format_daily_report_markdown(report: DailyReport, change_threshold_points: float, high_apy_threshold: float) -> str:
    lines = [f"### Barker 理财日报 {report.report_date.isoformat()}"]

    lines.append("")
    change_threshold = colored(f"{change_threshold_points:.2f}", COLOR_HIGH)
    lines.append(f"**昨日涨跌 >= {change_threshold} 个百分点：{len(report.rate_moves)} 条**")
    if report.rate_moves:
        shown_moves = report.rate_moves[:MAX_DAILY_REPORT_ITEMS]
        for index, move in enumerate(shown_moves, start=1):
            direction = "上涨" if move.delta > 0 else "下跌"
            color = rate_change_color(move.delta)
            lines.append(f"{index}. {move.campaign.protocol_name}｜{move.campaign.campaign_name}")
            lines.append(
                f"   {move.campaign.asset_symbol}｜{colored(format_percent(move.start_apy), color)} -> "
                f"{colored(format_percent(move.end_apy), color)}"
                f"｜{colored(f'{direction} {abs(move.delta):.2f}pct', color)}"
            )
        lines.extend(_remaining_line(len(report.rate_moves), len(shown_moves)))
    else:
        lines.append("- 无")

    lines.append("")
    high_threshold = colored(format_percent(high_apy_threshold), COLOR_HIGH)
    lines.append(f"**当前 APY > {high_threshold}：{len(report.high_apy_campaigns)} 条**")
    if report.high_apy_campaigns:
        shown_campaigns = report.high_apy_campaigns[:MAX_DAILY_REPORT_ITEMS]
        for index, campaign in enumerate(shown_campaigns, start=1):
            lines.append(f"{index}. {campaign.protocol_name}｜{campaign.campaign_name}")
            lines.append(f"   {campaign.asset_symbol}｜APY {colored(format_apy(campaign), COLOR_HIGH)}｜到期 {campaign.end_date}")
        lines.extend(_remaining_line(len(report.high_apy_campaigns), len(shown_campaigns)))
    else:
        lines.append("- 无")

    return "\n".join(lines)


def _remaining_line(total: int, shown: int) -> list[str]:
    if total <= shown:
        return []
    return [f"... 还有 {total - shown} 条未展示"]


def _snapshots_for_date(snapshots: list[dict[str, Any]], target_date: date) -> list[dict[str, Any]]:
    matched = []
    for snapshot in snapshots:
        timestamp = _parse_timestamp(str(snapshot.get("timestamp", "")))
        if timestamp and timestamp.astimezone(LOCAL_TZ).date() == target_date:
            matched.append(snapshot)
    return matched


def _detect_rate_moves(snapshots: list[dict[str, Any]], threshold_points: float) -> list[RateMove]:
    first_seen: dict[str, Campaign] = {}
    last_seen: dict[str, Campaign] = {}

    for snapshot in snapshots:
        campaigns = snapshot.get("campaigns", [])
        if not isinstance(campaigns, list):
            continue
        for raw_campaign in campaigns:
            if not isinstance(raw_campaign, dict):
                continue
            campaign = Campaign.from_dict(raw_campaign)
            first_seen.setdefault(campaign.uid, campaign)
            last_seen[campaign.uid] = campaign

    moves = []
    for uid, first_campaign in first_seen.items():
        last_campaign = last_seen.get(uid)
        if last_campaign is None:
            continue
        delta = last_campaign.apy - first_campaign.apy
        if abs(delta) >= threshold_points:
            moves.append(RateMove(last_campaign, first_campaign.apy, last_campaign.apy))

    return sorted(moves, key=lambda move: (-abs(move.delta), move.campaign.protocol_name, move.campaign.campaign_name))


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=LOCAL_TZ)
    return parsed

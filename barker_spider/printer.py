from __future__ import annotations

from .models import Campaign
from .notifier import format_apy


def format_campaign_table(campaigns: list[Campaign]) -> str:
    sorted_campaigns = sorted(
        campaigns,
        key=lambda campaign: (-campaign.apy, campaign.protocol_name, campaign.campaign_name),
    )
    rows = [
        [
            campaign.protocol_name,
            campaign.campaign_name,
            campaign.asset_symbol,
            campaign.end_date,
            format_apy(campaign),
        ]
        for campaign in sorted_campaigns
    ]
    return _markdown_table(["交易所", "活动", "代币", "到期时间", "实时年化"], rows)


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    table = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        table.append("| " + " | ".join(_clean_cell(cell) for cell in row) + " |")
    return "\n".join(table)


def _clean_cell(value: str) -> str:
    return str(value).replace("|", "/").replace("\n", " ").strip()

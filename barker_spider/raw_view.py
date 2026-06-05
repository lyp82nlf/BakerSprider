from __future__ import annotations

from typing import Any

from .fields import display_end_date, display_protocol, normalize_apy


KEY_FIELDS = ["protocol_uid", "campaign_name", "asset_symbol", "end_date", "campaign_apy"]


def format_raw_campaign_table(raw_items: list[dict[str, Any]]) -> str:
    rows = []
    for item in raw_items:
        protocol_uid = _text(item.get("protocol_uid"))
        campaign_name = _text(item.get("campaign_name"))
        asset_symbol = _text(item.get("asset_symbol"))
        end_date = _text(item.get("end_date"))
        campaign_apy_raw = _text(item.get("campaign_apy"))
        rows.append(
            [
                protocol_uid,
                display_protocol(protocol_uid) or "-",
                campaign_name or "-",
                asset_symbol or "-",
                end_date or "-",
                display_end_date(end_date),
                campaign_apy_raw or "-",
                _display_apy(campaign_apy_raw),
            ]
        )

    rows.sort(key=lambda row: row[2])
    return _markdown_table(
        ["protocol_uid", "交易所", "campaign_name", "asset_symbol", "end_date 原始值", "到期时间", "campaign_apy 原始值", "年化显示值"],
        rows,
    )


def _display_apy(value: str) -> str:
    try:
        return f"{normalize_apy(float(value)):.2f}%"
    except ValueError:
        return "-"


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


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

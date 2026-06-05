from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


PROTOCOL_NAMES = {
    "binance": "Binance",
    "bitget": "Bitget",
    "bybit": "Bybit",
    "gate": "Gate",
    "htx": "HTX",
    "mexc": "MEXC",
    "okx": "OKX",
    "osl": "OSL",
}


def normalize_apy(value: float) -> float:
    if abs(value) <= 1:
        return value * 100
    return value


def display_protocol(value: str) -> str:
    text = str(value).strip()
    if not text:
        return ""
    return PROTOCOL_NAMES.get(text.lower(), text.upper() if text.islower() else text)


def display_end_date(value: str) -> str:
    text = str(value).strip()
    if not text or text == "-":
        return "长期"

    parsed = _parse_iso_datetime(text)
    if parsed is None:
        return text

    local_dt = parsed.astimezone(ZoneInfo("Asia/Shanghai"))
    return local_dt.strftime("%Y-%m-%d %H:%M")


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed

from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class BarkerClientError(RuntimeError):
    pass


class BarkerClient:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout_seconds: int = 20,
        retries: int = 3,
        retry_delay_seconds: float = 2.0,
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.retry_delay_seconds = retry_delay_seconds

    def fetch_campaigns(self) -> list[dict[str, Any]]:
        payload = self._request_json()
        data = extract_campaign_list(payload)
        return [item for item in data if isinstance(item, dict)]


    def _request_json(self) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                request = Request(
                    self.api_url,
                    headers={
                        "accept": "application/json, text/plain, */*",
                        "referer": "https://app.barker.money/campaigns",
                        "user-agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/148.0.0.0 Safari/537.36"
                        ),
                        "x-api-key": self.api_key,
                    },
                    method="GET",
                )
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    body = response.read().decode("utf-8")
                    return json.loads(body)
            except HTTPError as exc:
                last_error = exc
                if 400 <= exc.code < 500 and exc.code != 429:
                    raise BarkerClientError(f"Barker API HTTP {exc.code}") from exc
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc

            if attempt < self.retries:
                time.sleep(self.retry_delay_seconds)

        raise BarkerClientError(f"Failed to fetch Barker campaigns: {last_error}") from last_error


def extract_campaign_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return _ensure_dict_list(payload, "top-level list")

    if not isinstance(payload, dict):
        raise BarkerClientError(f"Barker API returned unsupported JSON payload: {type(payload).__name__}")

    data = _find_list(payload)
    if data is None:
        raise BarkerClientError(f"Barker API payload does not contain a campaign list; {_payload_summary(payload)}")

    return _ensure_dict_list(data, "campaign list")


def _find_list(payload: Any) -> list[Any] | None:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return None

    preferred_keys = ("data", "list", "items", "records", "rows", "campaigns", "result", "results")
    for key in preferred_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
        nested = _find_list(value)
        if nested is not None:
            return nested

    for value in payload.values():
        nested = _find_list(value)
        if nested is not None:
            return nested

    return None


def _ensure_dict_list(data: list[Any], label: str) -> list[dict[str, Any]]:
    dict_items = [item for item in data if isinstance(item, dict)]
    if data and not dict_items:
        raise BarkerClientError(f"Barker API {label} contains no object items")
    return dict_items


def _payload_summary(payload: dict[str, Any]) -> str:
    keys = ", ".join(sorted(str(key) for key in payload.keys())) or "no keys"
    message = payload.get("message") or payload.get("msg") or payload.get("error")
    if message:
        return f"keys=[{keys}], message={message!r}"
    preview = json.dumps(payload, ensure_ascii=False)[:500]
    return f"keys=[{keys}], preview={preview}"

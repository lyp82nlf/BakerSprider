from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


DEFAULT_API_URL = "https://app.barker.money/api/protocols/campaigns?is_cex=1"


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Config:
    api_url: str
    api_key: str
    wecom_webhook_url: str
    request_timeout_seconds: int
    request_retries: int
    request_retry_delay_seconds: float
    fetch_interval_seconds: int
    rate_threshold_points: float
    only_active: bool
    state_path: Path
    history_path: Path
    report_state_path: Path
    daily_report_enabled: bool
    daily_report_hour: int
    daily_rate_change_threshold_points: float
    daily_high_apy_threshold: float
    log_level: str

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        return cls(
            api_url=os.getenv("BARKER_API_URL", DEFAULT_API_URL),
            api_key=os.getenv("BARKER_API_KEY", ""),
            wecom_webhook_url=os.getenv("WECOM_WEBHOOK_URL", ""),
            request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "45")),
            request_retries=int(os.getenv("REQUEST_RETRIES", "3")),
            request_retry_delay_seconds=float(os.getenv("REQUEST_RETRY_DELAY_SECONDS", "5")),
            fetch_interval_seconds=int(os.getenv("FETCH_INTERVAL_SECONDS", "300")),
            rate_threshold_points=float(os.getenv("RATE_THRESHOLD_POINTS", "1.0")),
            only_active=_bool_env("ONLY_ACTIVE", True),
            state_path=Path(os.getenv("STATE_PATH", "state/campaign_snapshot.json")),
            history_path=Path(os.getenv("HISTORY_PATH", "state/campaign_history.jsonl")),
            report_state_path=Path(os.getenv("REPORT_STATE_PATH", "state/report_state.json")),
            daily_report_enabled=_bool_env("DAILY_REPORT_ENABLED", True),
            daily_report_hour=int(os.getenv("DAILY_REPORT_HOUR", "10")),
            daily_rate_change_threshold_points=float(os.getenv("DAILY_RATE_CHANGE_THRESHOLD_POINTS", "2.0")),
            daily_high_apy_threshold=float(os.getenv("DAILY_HIGH_APY_THRESHOLD", "8.0")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    def validate_for_fetch(self) -> None:
        if not self.api_key:
            raise ValueError("BARKER_API_KEY is required")

    def validate_for_notify(self) -> None:
        if not self.wecom_webhook_url:
            raise ValueError("WECOM_WEBHOOK_URL is required unless --dry-run is used")

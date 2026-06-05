from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime

from .client import BarkerClient, BarkerClientError
from .config import Config
from .daily_report import LOCAL_TZ, build_daily_report, format_daily_report_markdown, should_send_daily_report
from .monitor import run_comparison
from .normalizer import normalize_campaigns
from .notifier import WeComNotifier, format_events_markdown
from .printer import format_campaign_table
from .raw_view import format_raw_campaign_table
from .state import CampaignHistory, CampaignState, ReportState


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = Config.from_env()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.command == "once":
        return run_once(config, dry_run=args.dry_run)
    if args.command == "run":
        return run_forever(config, dry_run=args.dry_run)
    if args.command == "list":
        return list_campaigns(config, refresh=args.refresh)
    if args.command == "daily-report":
        return send_daily_report(config, dry_run=args.dry_run, refresh=args.refresh)
    if args.command == "raw-list":
        return raw_list(config)

    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monitor Barker CEX campaigns.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    once = subparsers.add_parser("once", help="Fetch once, compare state, notify if needed.")
    once.add_argument("--dry-run", action="store_true", help="Print notification content instead of sending it.")

    run = subparsers.add_parser("run", help="Run forever with FETCH_INTERVAL_SECONDS interval.")
    run.add_argument("--dry-run", action="store_true", help="Print notification content instead of sending it.")

    list_parser = subparsers.add_parser("list", help="Print the latest saved campaign snapshot.")
    list_parser.add_argument("--refresh", action="store_true", help="Fetch latest campaigns before printing.")

    daily = subparsers.add_parser("daily-report", help="Build and send today's daily report.")
    daily.add_argument("--dry-run", action="store_true", help="Print daily report instead of sending it.")
    daily.add_argument("--refresh", action="store_true", help="Fetch latest campaigns before building the report.")

    subparsers.add_parser("raw-list", help="Fetch and print raw key fields from Barker API.")

    return parser


def run_forever(config: Config, dry_run: bool = False) -> int:
    while True:
        try:
            run_once(config, dry_run=dry_run)
        except BarkerClientError as exc:
            logging.warning("Monitor iteration skipped: %s", exc)
        except Exception:
            logging.exception("Monitor iteration failed")
        time.sleep(config.fetch_interval_seconds)


def run_once(config: Config, dry_run: bool = False) -> int:
    config.validate_for_fetch()
    if not dry_run:
        config.validate_for_notify()

    client = build_client(config)
    state = CampaignState(config.state_path)
    history = CampaignHistory(config.history_path)

    raw_campaigns = client.fetch_campaigns()
    campaigns = normalize_campaigns(raw_campaigns, only_active=config.only_active)
    history.append_snapshot(datetime.now(LOCAL_TZ).isoformat(), campaigns)
    previous = state.load()
    has_baseline = state.exists()
    events = run_comparison(
        previous=previous,
        current=campaigns,
        rate_threshold_points=config.rate_threshold_points,
        has_baseline=has_baseline,
    )
    state.save(campaigns)

    if not has_baseline:
        logging.info("Created baseline with %s active campaigns", len(campaigns))

    if events:
        content = format_events_markdown(events)
        if dry_run:
            print(content)
        else:
            WeComNotifier(config.wecom_webhook_url).send_markdown(content)
            logging.info("Sent WeCom notification with %s events", len(events))
    else:
        logging.info("No campaign changes detected; monitored %s active campaigns", len(campaigns))

    maybe_send_scheduled_daily_report(config, campaigns, dry_run=dry_run)
    return 0


def maybe_send_scheduled_daily_report(config: Config, campaigns: list, dry_run: bool = False) -> None:
    if not config.daily_report_enabled:
        return

    now = datetime.now(LOCAL_TZ)
    report_state = ReportState(config.report_state_path)
    if not should_send_daily_report(now, config.daily_report_hour, report_state.last_report_date()):
        return

    content = build_daily_report_content(config, campaigns, now)
    if dry_run:
        print(content)
    else:
        WeComNotifier(config.wecom_webhook_url).send_markdown(content)
        logging.info("Sent daily WeCom report")
        report_state.save_last_report_date(now.date().isoformat())


def list_campaigns(config: Config, refresh: bool = False) -> int:
    state = CampaignState(config.state_path)
    if refresh:
        config.validate_for_fetch()
        client = build_client(config)
        campaigns = normalize_campaigns(client.fetch_campaigns(), only_active=config.only_active)
        state.save(campaigns)

    campaigns = list(state.load().values())
    if not campaigns:
        print(f"No saved campaigns found at {config.state_path}. Run `python3 -m barker_spider once --dry-run` first.")
        return 1

    print(format_campaign_table(campaigns))
    return 0


def raw_list(config: Config) -> int:
    config.validate_for_fetch()
    client = build_client(config)
    print(format_raw_campaign_table(client.fetch_campaigns()))
    return 0


def send_daily_report(config: Config, dry_run: bool = False, refresh: bool = False) -> int:
    if not dry_run:
        config.validate_for_notify()

    state = CampaignState(config.state_path)
    if refresh:
        config.validate_for_fetch()
        client = build_client(config)
        campaigns = normalize_campaigns(client.fetch_campaigns(), only_active=config.only_active)
        CampaignHistory(config.history_path).append_snapshot(datetime.now(LOCAL_TZ).isoformat(), campaigns)
        state.save(campaigns)

    campaigns = list(state.load().values())
    if not campaigns:
        print(f"No saved campaigns found at {config.state_path}. Run `python3 -m barker_spider once --dry-run` first.")
        return 1

    content = build_daily_report_content(config, campaigns, datetime.now(LOCAL_TZ))
    if dry_run:
        print(content)
    else:
        WeComNotifier(config.wecom_webhook_url).send_markdown(content)
        logging.info("Sent daily WeCom report")
    return 0


def build_daily_report_content(config: Config, campaigns: list, now: datetime) -> str:
    report = build_daily_report(
        snapshots=CampaignHistory(config.history_path).load_snapshots(),
        current_campaigns=campaigns,
        now=now,
        change_threshold_points=config.daily_rate_change_threshold_points,
        high_apy_threshold=config.daily_high_apy_threshold,
    )
    return format_daily_report_markdown(
        report,
        change_threshold_points=config.daily_rate_change_threshold_points,
        high_apy_threshold=config.daily_high_apy_threshold,
    )


def build_client(config: Config) -> BarkerClient:
    return BarkerClient(
        config.api_url,
        config.api_key,
        timeout_seconds=config.request_timeout_seconds,
        retries=config.request_retries,
        retry_delay_seconds=config.request_retry_delay_seconds,
    )


if __name__ == "__main__":
    sys.exit(main())

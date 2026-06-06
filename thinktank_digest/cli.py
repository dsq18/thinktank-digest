from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .logging_utils import configure_logging
from .sources import SourceRegistryError, apply_natural_command, load_sources


PROJECT_ROOT = Path.cwd()
DEFAULT_SOURCES = PROJECT_ROOT / "sources.yaml"
DEFAULT_DB = PROJECT_ROOT / "data" / "thinktank_digest.sqlite"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thinktank-digest")
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--log-level", default="INFO")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="discover, analyze, render, and optionally email")
    run.add_argument("--no-send", action="store_true", help="render report without sending email")
    run.add_argument("--max-articles", type=int, default=60)
    run.add_argument("--html-out", type=Path)
    run.add_argument("--text-out", type=Path)

    staging = subparsers.add_parser("staging", help="run deterministic end-to-end staging workflow")
    staging.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR / "staging")

    review = subparsers.add_parser("self-review", help="compile, test, and run staging workflow")
    review.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR / "self-review")
    review.add_argument("--skip-pytest", action="store_true")

    subparsers.add_parser("check-email-env", help="verify required NetEase SMTP environment variables")

    smoke = subparsers.add_parser("send-test-email", help="send a real SMTP smoke-test email")
    smoke.add_argument("--subject", default="ThinkTank-Digest SMTP 测试")

    subparsers.add_parser("list-sources", help="list configured sources")

    command = subparsers.add_parser("source-command", help="apply a natural source command")
    command.add_argument("text", help='e.g. "Disable source Brookings"')
    command.add_argument("--website", default="")
    command.add_argument("--rss", default="")
    command.add_argument("--priority", type=int, default=3)
    command.add_argument("--topics", default="", help="comma-separated topic list for Add source")
    command.add_argument("--tags", default="", help="comma-separated tag list for Add source")

    return parser


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _db_for_command(command: str, configured_db: Path) -> Path:
    if configured_db != DEFAULT_DB:
        return configured_db
    if command == "staging":
        return PROJECT_ROOT / "data" / "staging.sqlite"
    if command == "self-review":
        return PROJECT_ROOT / "data" / "self_review.sqlite"
    return configured_db


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)
    db_path = _db_for_command(args.command, args.db)

    try:
        if args.command == "run":
            from .pipeline import run_daily_digest
            from .report import render_html, render_plain_text

            report = run_daily_digest(
                sources_path=args.sources,
                db_path=db_path,
                send=not args.no_send,
                max_articles=args.max_articles,
            )
            if args.html_out:
                args.html_out.parent.mkdir(parents=True, exist_ok=True)
                args.html_out.write_text(render_html(report), encoding="utf-8")
            if args.text_out:
                args.text_out.parent.mkdir(parents=True, exist_ok=True)
                args.text_out.write_text(render_plain_text(report), encoding="utf-8")
            print(f"Generated report with {len(report.all_items)} analyzed articles.")
            return

        if args.command == "staging":
            from .staging import run_staging_workflow

            result = run_staging_workflow(
                sources_path=args.sources,
                db_path=db_path,
                out_dir=args.out_dir,
            )
            print(f"Staging complete: {result}")
            return

        if args.command == "self-review":
            from .self_review import run_self_review

            result = run_self_review(
                project_root=PROJECT_ROOT,
                sources_path=args.sources,
                db_path=db_path,
                out_dir=args.out_dir,
                skip_pytest=args.skip_pytest,
            )
            print(f"Self-review complete: {result}")
            return

        if args.command == "check-email-env":
            from .emailer import validate_email_environment

            validate_email_environment()
            print("Email environment OK.")
            return

        if args.command == "send-test-email":
            from .emailer import send_email

            recipient = send_email(
                args.subject,
                "<p>ThinkTank-Digest SMTP 测试邮件。若你收到此邮件，NetEase SMTP 配置可用。</p>",
                "ThinkTank-Digest SMTP 测试邮件。若你收到此邮件，NetEase SMTP 配置可用。",
            )
            print(f"SMTP smoke test delivered to {recipient}.")
            return

        if args.command == "list-sources":
            for source in load_sources(args.sources):
                state = "enabled" if source.enabled else "disabled"
                print(f"{source.name}\t{state}\tpriority={source.priority}\trss={source.rss or '-'}")
            return

        if args.command == "source-command":
            result = apply_natural_command(
                args.sources,
                args.text,
                website=args.website,
                rss=args.rss,
                priority=args.priority,
                topics=_split_csv(args.topics),
                tags=_split_csv(args.tags),
            )
            print(result)
            return
    except SourceRegistryError as exc:
        print(f"Source registry error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

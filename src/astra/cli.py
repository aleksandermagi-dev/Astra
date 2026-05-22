from __future__ import annotations

import argparse
import csv
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import re
import sys
from typing import Sequence

from .analyze import load_performance_records, summarize_performance
from .config import AstraConfig
from .formatters import (
    format_campaign_plan_markdown,
    format_experiment_suggestions,
    format_feedback_summary,
    format_ideas_text,
    format_posts_json,
    format_posts_markdown,
    format_posts_text,
    format_queue_summary,
    format_reply_draft_markdown,
    format_workflow_items_text,
    write_output,
)
from .models import (
    AnalyticsLogEntry,
    ContentPost,
    MarketLogEntry,
    VALID_REPLY_SCENARIOS,
    VALID_IDEA_PLATFORMS,
    VALID_POST_TIME_SLOTS,
    VALID_WORKFLOW_PLATFORMS,
    WorkflowContentItem,
)
from .outputs import (
    append_analytics_log,
    load_publish_log,
    approve_content_item,
    create_batch_run_dir,
    find_content_item_path,
    load_content_items,
    mark_content_item_posted,
    queue_content_item,
    review_draft_items,
    review_queue_items,
    save_batch_items,
    save_generated_output,
    ensure_output_dirs,
    load_content_item,
    load_recent_content_items,
    write_content_item,
)
from .production import ProductionPipeline, ProductionPipelineError
from .publisher import PublishingService
from .safety_layer import AstraSafetyLayer
from .service import AstraGenerator
from .tendril import TendrilService


FORMAT_EXTENSIONS = {
    "text": "txt",
    "json": "json",
    "md": "md",
}

KNOWN_COMMANDS = {
    "ideas",
    "batch",
    "format",
    "market-log-template",
    "products",
    "campaign",
    "posts",
    "replies",
    "feedback",
    "experiments",
    "accounts",
    "publish",
    "publish-queue",
    "publish-log",
    "review-drafts",
    "approve",
    "queue",
    "review-queue",
    "mark-posted",
    "log-post",
    "analyze",
    "produce",
    "tendril",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="astra", description="Astra PR and marketing operator CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ideas_parser = subparsers.add_parser("ideas", help="Generate ranked PR and campaign ideas")
    ideas_parser.add_argument("--topic")
    ideas_parser.add_argument("--count", type=int)
    ideas_parser.add_argument("--platform", choices=sorted(VALID_IDEA_PLATFORMS), default=None)
    ideas_parser.add_argument("--config")

    batch_parser = subparsers.add_parser("batch", help="Generate master PR/campaign drafts")
    batch_parser.add_argument("--topic")
    batch_parser.add_argument("--input")
    batch_parser.add_argument("--count", type=int)
    batch_parser.add_argument("--format", choices=["text", "json", "md"], default="text")
    batch_parser.add_argument("--output")
    batch_parser.add_argument("--config")

    format_parser = subparsers.add_parser("format", help="Format master drafts for a marketing channel")
    format_parser.add_argument("--input", required=True)
    format_parser.add_argument("--platform", choices=sorted(VALID_WORKFLOW_PLATFORMS), required=True)
    format_parser.add_argument("--config")

    review_drafts_parser = subparsers.add_parser("review-drafts", help="List draft items")
    review_drafts_parser.add_argument("--config")

    market_log_parser = subparsers.add_parser("market-log-template", help="Print a simple market response log template")
    market_log_parser.add_argument("--format", choices=["csv", "md"], default="md")
    market_log_parser.add_argument("--save", action="store_true")

    products_parser = subparsers.add_parser("products", help="Inspect LinnuteeInnovations product profiles")
    products_subparsers = products_parser.add_subparsers(dest="products_command", required=True)
    products_subparsers.add_parser("list", help="List product profiles")
    products_show = products_subparsers.add_parser("show", help="Show one product profile")
    products_show.add_argument("name")
    products_show.add_argument("--config")

    campaign_parser = subparsers.add_parser("campaign", help="Create product campaign plans")
    campaign_subparsers = campaign_parser.add_subparsers(dest="campaign_command", required=True)
    campaign_create = campaign_subparsers.add_parser("create", help="Create a product campaign")
    campaign_create.add_argument("--product", default=None)
    campaign_create.add_argument("--goal", required=True)
    campaign_create.add_argument("--days", type=int, default=7)
    campaign_create.add_argument("--config")

    posts_parser = subparsers.add_parser("posts", help="Draft product posts")
    posts_subparsers = posts_parser.add_subparsers(dest="posts_command", required=True)
    posts_draft = posts_subparsers.add_parser("draft", help="Draft platform-native product posts")
    posts_draft.add_argument("--product", default=None)
    posts_draft.add_argument("--channel", choices=sorted(VALID_WORKFLOW_PLATFORMS), required=True)
    posts_draft.add_argument("--count", type=int, default=5)
    posts_draft.add_argument("--goal")
    posts_draft.add_argument("--config")

    replies_parser = subparsers.add_parser("replies", help="Draft public reply templates")
    replies_subparsers = replies_parser.add_subparsers(dest="replies_command", required=True)
    replies_draft = replies_subparsers.add_parser("draft", help="Draft a reply")
    replies_draft.add_argument("--product", default=None)
    replies_draft.add_argument("--scenario", choices=sorted(VALID_REPLY_SCENARIOS), required=True)
    replies_draft.add_argument("--user-signal")
    replies_draft.add_argument("--config")

    feedback_parser = subparsers.add_parser("feedback", help="Summarize market response logs")
    feedback_subparsers = feedback_parser.add_subparsers(dest="feedback_command", required=True)
    feedback_summary = feedback_subparsers.add_parser("summarize", help="Summarize a market log file")
    feedback_summary.add_argument("--input", required=True)

    experiments_parser = subparsers.add_parser("experiments", help="Suggest product marketing experiments")
    experiments_subparsers = experiments_parser.add_subparsers(dest="experiments_command", required=True)
    experiments_suggest = experiments_subparsers.add_parser("suggest", help="Suggest experiments from market response")
    experiments_suggest.add_argument("--product", default=None)
    experiments_suggest.add_argument("--input", required=True)

    accounts_parser = subparsers.add_parser("accounts", help="Inspect publishing account connectors")
    accounts_subparsers = accounts_parser.add_subparsers(dest="accounts_command", required=True)
    accounts_subparsers.add_parser("status", help="Show account connector status")

    publish_parser = subparsers.add_parser("publish", help="Publish one queued item")
    publish_parser.add_argument("--input")
    publish_parser.add_argument("--id")

    publish_queue_parser = subparsers.add_parser("publish-queue", help="Publish queued items")
    publish_queue_parser.add_argument("--platform", choices=["bluesky"], default="bluesky")

    subparsers.add_parser("publish-log", help="Show publish audit log")

    approve_parser = subparsers.add_parser("approve", help="Approve a draft item")
    approve_parser.add_argument("--input")
    approve_parser.add_argument("--id")

    queue_parser = subparsers.add_parser("queue", help="Queue an approved item")
    queue_parser.add_argument("--input")
    queue_parser.add_argument("--id")
    queue_parser.add_argument("--slot", choices=sorted(VALID_POST_TIME_SLOTS))

    review_queue_parser = subparsers.add_parser("review-queue", help="Review queued items")
    review_queue_parser.add_argument("--config")

    mark_posted_parser = subparsers.add_parser("mark-posted", help="Mark a queued item as posted")
    mark_posted_parser.add_argument("--input")
    mark_posted_parser.add_argument("--id")

    log_post_parser = subparsers.add_parser("log-post", help="Append a post analytics stub entry")
    log_post_parser.add_argument("--input")
    log_post_parser.add_argument("--id")
    log_post_parser.add_argument("--platform")
    log_post_parser.add_argument("--topic")
    log_post_parser.add_argument("--date-posted")
    log_post_parser.add_argument("--post-id-or-url", required=True)
    log_post_parser.add_argument("--views", type=float)
    log_post_parser.add_argument("--likes", type=float)
    log_post_parser.add_argument("--comments", type=float)
    log_post_parser.add_argument("--notes", default="")

    produce_parser = subparsers.add_parser("produce", help="Render approved content into ready media")
    produce_parser.add_argument("--input")
    produce_parser.add_argument("--id")
    produce_parser.add_argument("--config")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze performance metadata")
    analyze_parser.add_argument("--input", required=True)

    tendril_parser = subparsers.add_parser("tendril", help="Run Astra-local approved Tendril workflows")
    tendril_subparsers = tendril_parser.add_subparsers(dest="tendril_command", required=True)

    tendril_create = tendril_subparsers.add_parser("create", help="Create a Tendril task plan")
    tendril_create.add_argument("--goal", required=True)
    tendril_create.add_argument("--session-id", default="default")
    tendril_create.add_argument("--project-id")
    tendril_create.add_argument("--workspace-name")

    for name in ("approve", "run", "show", "audit", "archive"):
        command = tendril_subparsers.add_parser(name, help=f"{name.title()} a Tendril task")
        command.add_argument("task_id")

    tendril_list = tendril_subparsers.add_parser("list", help="List Tendril tasks")
    tendril_list.add_argument("--session-id")
    tendril_list.add_argument("--project-id")
    tendril_list.add_argument("--status")
    tendril_list.add_argument("--include-archived", action="store_true")
    tendril_list.add_argument("--limit", type=int, default=50)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return run_cli(argv or sys.argv[1:])


def run_cli(
    argv: Sequence[str],
    *,
    stdout: io.TextIOBase | None = None,
    stderr: io.TextIOBase | None = None,
    generator_factory=AstraGenerator,
    pipeline_factory=ProductionPipeline,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    _configure_stream(stdout)
    _configure_stream(stderr)
    argv = _normalize_cli_argv(argv)
    parser = build_parser()
    args = parser.parse_args(list(argv))

    with redirect_stdout(stdout), redirect_stderr(stderr):
        if args.command == "analyze":
            records = load_performance_records(args.input)
            print(summarize_performance(records))
            return 0

        if args.command == "market-log-template":
            rendered = _render_market_log_template(args.format)
            print(rendered)
            if args.save:
                path = save_generated_output(
                    content=rendered,
                    topic="market response",
                    kind="logs",
                    extension="csv" if args.format == "csv" else "md",
                )
                print(f"\nSaved market log: {path}")
            return 0

        if args.command == "products":
            config = AstraConfig.load(getattr(args, "config", None))
            return _run_products_command(args, config)

        if args.command in {"accounts", "publish", "publish-queue", "publish-log"}:
            return _run_publish_command(args)

        if args.command in {"feedback", "experiments"}:
            return _run_signal_command(args)

        if args.command == "tendril":
            try:
                return _run_tendril_command(args)
            except ValueError as exc:
                print(str(exc), file=stderr)
                return 2

        if args.command in {"approve", "queue", "mark-posted", "log-post"}:
            try:
                return _run_workflow_command(args)
            except ValueError as exc:
                print(str(exc), file=stderr)
                return 2

        if args.command == "review-drafts":
            items = review_draft_items()
            print(format_queue_summary(items))
            return 0

        if args.command == "review-queue":
            items = review_queue_items()
            print(format_queue_summary(items))
            return 0

        if args.command == "produce":
            input_path = _resolve_item_input(getattr(args, "input", None), getattr(args, "id", None))
            item = _refresh_item_safety(input_path)
            if item.status != "approved":
                print("Only approved items can be produced into ready media.", file=stderr)
                return 2
            if item.safety.decision != "PASS":
                print("Only safety PASS items can be produced into ready media.", file=stderr)
                return 2
            config = AstraConfig.load(getattr(args, "config", None))
            pipeline = pipeline_factory(config)
            try:
                result = pipeline.produce(item)
            except ProductionPipelineError as exc:
                print(str(exc), file=stderr)
                for name, path in exc.artifacts.items():
                    print(f"{name}: {path}", file=stderr)
                return 1
            except ValueError as exc:
                print(str(exc), file=stderr)
                return 2

            print(f"Ready media saved to: {result.ready_dir}")
            for name, path in result.artifacts.items():
                print(f"{name}: {path}")
            return 0

        config = AstraConfig.load(getattr(args, "config", None))
        if not config.api_key:
            print("OPENAI_API_KEY is required for generation commands.", file=stderr)
            return 2

        if args.command in {"campaign", "posts", "replies"}:
            try:
                config = config.with_product(getattr(args, "product", None))
            except ValueError as exc:
                print(str(exc), file=stderr)
                return 2

        generator = generator_factory(config)

        if args.command == "campaign":
            plan = generator.generate_campaign_plan(goal=args.goal, days=args.days)
            rendered = format_campaign_plan_markdown(plan)
            print(rendered)
            saved_path = save_generated_output(
                content=rendered,
                topic=f"{plan.product} {args.goal}",
                kind="campaigns",
                extension="md",
            )
            print(f"\nSaved campaign plan: {saved_path}")
            return 0

        if args.command == "posts":
            recent_items = load_recent_content_items()
            items = generator.draft_product_posts(
                channel=args.channel,
                count=args.count,
                goal=args.goal,
                recent_items=recent_items,
            )
            batch_dir = create_batch_run_dir()
            saved_paths = save_batch_items(items, batch_dir)
            print(format_workflow_items_text(items))
            print("")
            for path in saved_paths:
                print(f"Saved post draft: {path}")
            return 0

        if args.command == "replies":
            reply = generator.draft_reply(scenario=args.scenario, user_signal=args.user_signal)
            rendered = format_reply_draft_markdown(reply)
            print(rendered)
            saved_path = save_generated_output(
                content=rendered,
                topic=f"{reply.product} {reply.scenario}",
                kind="replies",
                extension="md",
            )
            print(f"\nSaved reply draft: {saved_path}")
            return 0

        if args.command == "ideas":
            platform = args.platform or config.default_platform
            count = args.count or config.default_count
            ideas = generator.generate_ideas(topic=args.topic, count=count, platform=platform)
            rendered = format_ideas_text(ideas)
            print(rendered)
            saved_path = save_generated_output(content=rendered, topic=args.topic, kind="ideas")
            print(f"\nSaved to: {saved_path}")
            return 0

        if args.command == "batch":
            if not args.topic and not args.input:
                print("Provide --topic or --input for batch generation.", file=stderr)
                return 2
            topics = [args.topic] if args.topic else _load_topics(args.input)
            count = args.count or config.default_count
            all_posts = []
            saved_paths: list[Path] = []
            safety_summaries: list[str] = []
            recent_items = load_recent_content_items()
            for topic in topics:
                items = generator.generate_workflow_items(topic=topic, count=count, recent_items=recent_items)
                all_posts.extend(
                    [
                        ContentPost(
                            topic=item.topic,
                            hook=item.hook,
                            script_lines=item.script_lines,
                            caption=item.caption,
                            tags=item.hashtags,
                            platform_notes=item.platform_notes,
                            retention_check=item.retention_check,
                            suggested_post_time=item.suggested_post_time,
                        )
                        for item in items
                    ]
                )
                batch_dir = create_batch_run_dir()
                saved_paths.extend(save_batch_items(items, batch_dir))
                safety_summaries.extend(_format_safety_summary(item) for item in items)

            rendered = _render_posts(all_posts, args.format)
            if args.output:
                write_output(args.output, rendered)
                print(f"Saved summary to: {Path(args.output).resolve()}")
            else:
                print(rendered)
            print("")
            for path in saved_paths:
                print(f"Saved draft item: {path}")
            if safety_summaries:
                print("")
                for line in safety_summaries:
                    print(line)
            return 0

        if args.command == "format":
            formatted_items = []
            saved_paths = []
            safety_summaries = []
            recent_items = load_recent_content_items()
            for item in load_content_items(args.input):
                if item.workflow_stage != "master":
                    continue
                formatted = generator.format_for_platform(item, args.platform, recent_items=recent_items)
                formatted_items.append(formatted)
                saved_paths.append(_save_formatted_item(args.input, formatted))
                safety_summaries.append(_format_safety_summary(formatted))
            print(format_workflow_items_text(formatted_items) if formatted_items else "No master drafts found to format.")
            if saved_paths:
                print("")
                for path in saved_paths:
                    print(f"Saved formatted item: {path}")
            if safety_summaries:
                print("")
                for line in safety_summaries:
                    print(line)
            return 0

        return 0


def _run_products_command(args: argparse.Namespace, config: AstraConfig) -> int:
    if args.products_command == "list":
        for key, profile in config.products.items():
            default_marker = " (default)" if key == config.default_product else ""
            print(f"{key}: {profile.name}{default_marker}")
        print("company: LinnuteeInnovations")
        return 0
    product = config.get_product(args.name)
    if product is None:
        print(f"Company: {config.company_name}")
        print(config.company_role)
        return 0
    print(json.dumps(product.to_mapping(), indent=2))
    return 0


def _run_signal_command(args: argparse.Namespace) -> int:
    entries = _load_market_log_entries(args.input)
    if args.command == "feedback":
        rendered = format_feedback_summary(entries)
        print(rendered)
        saved_path = save_generated_output(content=rendered, topic="market feedback", kind="feedback", extension="md")
        print(f"\nSaved feedback summary: {saved_path}")
        return 0
    rendered = format_experiment_suggestions(entries)
    print(rendered)
    saved_path = save_generated_output(content=rendered, topic="market experiments", kind="experiments", extension="md")
    print(f"\nSaved experiment suggestions: {saved_path}")
    return 0


def _run_publish_command(args: argparse.Namespace) -> int:
    if args.command == "publish-log":
        results = load_publish_log()
        if not results:
            print("Publish log is empty.")
            return 0
        for result in results:
            print(_format_publish_result(result))
        return 0

    service = PublishingService()
    if args.command == "accounts":
        status = service.accounts_status()
        for platform, value in status.items():
            print(f"{platform}: {value}")
        return 0

    if args.command == "publish":
        try:
            if args.input:
                result = service.publish_path(args.input)
            elif args.id:
                result = service.publish_id(args.id)
            else:
                raise ValueError("Provide --input or --id.")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(_format_publish_result(result))
        return 0 if result.status == "posted" else 1

    results = service.publish_queue(platform=args.platform)
    if not results:
        print(f"No queued items found for {args.platform}.")
        return 0
    for result in results:
        print(_format_publish_result(result))
    return 0 if all(result.status == "posted" for result in results) else 1


def _format_publish_result(result) -> str:
    if result.status == "posted":
        target = result.external_url or result.external_id or "posted"
        return f"{result.item_id} | {result.platform} | posted | {target}"
    return f"{result.item_id} | {result.platform} | failed | {result.error}"


def _run_workflow_command(args: argparse.Namespace) -> int:
    if args.command == "approve":
        input_path = _resolve_item_input(getattr(args, "input", None), getattr(args, "id", None))
        item = _refresh_item_safety(input_path)
        if item.safety.decision != "PASS":
            raise ValueError("Only safety PASS items can be approved.")
        target = approve_content_item(input_path)
        print(f"Approved: {target}")
        return 0

    if args.command == "queue":
        input_path = _resolve_item_input(getattr(args, "input", None), getattr(args, "id", None))
        item = _refresh_item_safety(input_path, posting_only=True)
        if item.safety.decision != "PASS":
            raise ValueError("Posting safety failed. Keep this item in draft or rewrite it before queueing.")
        target = queue_content_item(input_path, slot=args.slot)
        print(f"Queued: {target}")
        return 0

    if args.command == "mark-posted":
        input_path = _resolve_item_input(getattr(args, "input", None), getattr(args, "id", None))
        target = mark_content_item_posted(input_path)
        print(f"Marked as posted: {target}")
        return 0

    input_path = None
    if getattr(args, "input", None) or getattr(args, "id", None):
        input_path = _resolve_item_input(getattr(args, "input", None), getattr(args, "id", None))
    item = load_content_items(input_path)[0] if input_path else None
    payload = {
        "platform": args.platform or (item.platform if item else ""),
        "topic": args.topic or (item.topic if item else ""),
        "date_posted": args.date_posted or (item.suggested_post_time if item else ""),
        "post_id_or_url": args.post_id_or_url,
        "views": args.views,
        "likes": args.likes,
        "comments": args.comments,
        "notes": args.notes,
    }
    entry = AnalyticsLogEntry.from_mapping(payload)
    path = append_analytics_log(entry)
    print(f"Logged analytics to: {path}")
    return 0


def _run_tendril_command(args: argparse.Namespace) -> int:
    service = TendrilService()
    command = args.tendril_command
    if command == "create":
        payload = service.create_task(
            goal=args.goal,
            session_id=args.session_id,
            project_id=args.project_id,
            workspace_name=args.workspace_name,
        )
    elif command == "approve":
        payload = service.approve_task(args.task_id)
    elif command == "run":
        payload = service.run_task(args.task_id)
    elif command == "show":
        payload = service.show_task(args.task_id)
    elif command == "list":
        payload = service.list_tasks(
            session_id=args.session_id,
            project_id=args.project_id,
            status=args.status,
            include_archived=args.include_archived,
            limit=args.limit,
        )
    elif command == "audit":
        payload = service.audit_report(args.task_id)
    elif command == "archive":
        payload = service.archive_task(args.task_id)
    else:
        raise ValueError(f"Unknown Tendril command: {command}")
    print(_format_tendril_payload(payload))
    return 0


def _format_tendril_payload(payload: dict[str, object]) -> str:
    schema_type = str(payload.get("schema_type") or "")
    if schema_type == "tendril_task_list":
        tasks = list(payload.get("tasks") or [])
        if not tasks:
            return "No Tendril tasks found."
        return "\n".join(_format_tendril_task_line(dict(task)) for task in tasks)
    if schema_type == "tendril_audit_report":
        task = dict(payload.get("task") or {})
        events = list(payload.get("events") or [])
        lines = [f"Audit for {task.get('id')}: {task.get('goal')}", f"Events: {len(events)}"]
        for event in events:
            event_payload = dict(event)
            lines.append(
                f"- {event_payload.get('event_type')} | {event_payload.get('action_taken') or 'no action'} | {event_payload.get('created_at')}"
            )
        return "\n".join(lines)
    if schema_type == "tendril_run_result":
        task = dict(payload.get("task") or {})
        lines = [
            f"Tendril run: {payload.get('status')}",
            _format_tendril_task_line(task),
            f"Completed steps: {payload.get('completed_steps', 0)}",
        ]
        changed_paths = [str(path) for path in payload.get("changed_paths") or []]
        if changed_paths:
            lines.append("Changed paths:")
            lines.extend(f"- {path}" for path in changed_paths)
        failed_step = payload.get("failed_step")
        if failed_step:
            step = dict(failed_step)
            lines.append(f"Failed step: {step.get('id')} | {step.get('failure_details')}")
        if payload.get("reason"):
            lines.append(f"Reason: {payload.get('reason')}")
        return "\n".join(lines)
    if schema_type == "tendril_archive_result":
        task = dict(payload.get("task") or {})
        return "Archived: " + _format_tendril_task_line(task)
    if schema_type == "tendril_task":
        task = dict(payload.get("task") or {})
        plan = dict(payload.get("plan") or {})
        steps = [dict(step) for step in payload.get("steps") or []]
        lines = [
            _format_tendril_task_line(task),
            f"Plan: {plan.get('id') or 'none'}",
            f"Steps: {len(steps)}",
            f"Approval required: {payload.get('approval_required')}",
            f"Advisory until approved: {payload.get('advisory_until_approved')}",
        ]
        for step in steps:
            lines.append(
                f"- {step.get('step_index')}: {step.get('local_action') or step.get('action_type')} | {step.get('status')} | approval={bool(step.get('approval_required'))}"
            )
        return "\n".join(lines)
    return json.dumps(payload, indent=2)


def _format_tendril_task_line(task: dict[str, object]) -> str:
    return (
        f"{task.get('id')} | {task.get('status')} | approval={task.get('approval_state')} | "
        f"{task.get('goal')}"
    )


def _resolve_item_input(input_path: str | None, item_id: str | None) -> str:
    if input_path:
        return input_path
    if item_id:
        return str(find_content_item_path(item_id))
    raise ValueError("Provide --input or --id.")


def _save_formatted_item(input_path: str, item: WorkflowContentItem) -> Path:
    source = Path(input_path)
    target_dir = source if source.is_dir() else source.parent
    return save_batch_items([item], target_dir)[0]


def _load_topics(path: str) -> list[str]:
    file_path = Path(path)
    if file_path.suffix.lower() == ".json":
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("topics", [])
        return [str(item).strip() for item in data if str(item).strip()]
    return [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _render_posts(posts, fmt: str) -> str:
    if fmt == "json":
        return format_posts_json(posts)
    if fmt == "md":
        return format_posts_markdown(posts)
    return format_posts_text(posts)


def _configure_stream(stream: io.TextIOBase) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(errors="replace")
        except (TypeError, ValueError):
            pass


def _normalize_cli_argv(argv: Sequence[str]) -> list[str]:
    tokens = list(argv)
    if not tokens:
        return tokens
    first = tokens[0]
    if first in {"ideas", "batch", "format"} and len(tokens) > 1 and not any(
        token.startswith("--") for token in tokens[1:]
    ):
        return _interpret_conversational_request(" ".join(tokens))
    if first in KNOWN_COMMANDS or first.startswith("-"):
        return tokens
    return _interpret_conversational_request(" ".join(tokens))


def _interpret_conversational_request(request: str) -> list[str]:
    text = request.strip()
    lowered = text.lower()

    if any(phrase in lowered for phrase in ("review queue", "show queue", "open queue")):
        return ["review-queue"]

    if any(phrase in lowered for phrase in ("review drafts", "show drafts", "list drafts")):
        return ["review-drafts"]

    if "format" in lowered:
        platform = _extract_platform(lowered)
        if not platform:
            raise ValueError("Could not infer a channel. Try mentioning Reddit, Hacker News, X/Bluesky, Dev.to, or another supported channel.")
        batch_dir = _latest_batch_dir()
        if batch_dir is None:
            raise ValueError("No batch folder found to format. Generate a batch first.")
        return ["format", "--input", str(batch_dir), "--platform", platform]

    count = _extract_count(lowered)
    topic = _extract_topic(text)

    if "idea" in lowered:
        args = ["ideas"]
        if topic:
            args.extend(["--topic", topic])
        if count:
            args.extend(["--count", str(count)])
        platform = _extract_platform(lowered)
        if platform:
            args.extend(["--platform", platform])
        return args

    if any(phrase in lowered for phrase in ("generate", "write", "make", "create", "batch", "draft")):
        args = ["batch"]
        if topic:
            args.extend(["--topic", topic])
        if count:
            args.extend(["--count", str(count)])
        return args

    raise ValueError(
        "Could not understand that request. Try something like: "
        '"generate me 3 on why attention is harder to keep than ever" or '
        '"give me 10 ideas about trust and attention".'
    )


def _extract_count(text: str) -> int | None:
    match = re.search(r"\b(\d{1,2})\b", text)
    return int(match.group(1)) if match else None


def _extract_platform(text: str) -> str | None:
    if "hacker news" in text or "show hn" in text:
        return "hacker_news"
    if "indie hackers" in text or "indiehackers" in text:
        return "indie_hackers"
    if "x/bluesky" in text or "x bluesky" in text or "bluesky" in text or re.search(r"\bx\b", text):
        return "x_bluesky"
    if "dev.to" in text or "devto" in text:
        return "devto"
    if "reddit" in text:
        return "reddit"
    if "email" in text or "newsletter" in text:
        return "email_update"
    if "reply" in text or "response" in text:
        return "direct_reply"
    if "youtube shorts" in text or "shorts" in text:
        return "youtube_shorts"
    if "tiktok" in text:
        return "tiktok"
    return None


def _extract_topic(text: str) -> str | None:
    match = re.search(r"\b(?:on|about)\s+(.+)$", text, flags=re.IGNORECASE)
    if match:
        topic = match.group(1).strip(" .!?\"'")
        topic = re.sub(
            r"\s+for\s+(reddit|hacker news|show hn|indie hackers|indiehackers|x/bluesky|x bluesky|bluesky|dev\.to|devto|email|newsletter|reply|response|tiktok|youtube shorts|shorts)$",
            "",
            topic,
            flags=re.IGNORECASE,
        )
        return topic.strip(" .!?\"'")
    cleaned = re.sub(
        r"\b(generate|give|make|create|write|me|some|a|an|batch|drafts?|ideas?|for|please|\d+)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    topic = " ".join(cleaned.split()).strip(" .!?\"'")
    return topic or None


def _latest_batch_dir() -> Path | None:
    batches_root = ensure_output_dirs()["batches"]
    candidates = [path for path in batches_root.glob("*") if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _render_market_log_template(fmt: str) -> str:
    columns = [
        "date",
        "platform",
        "post_url",
        "angle",
        "cta",
        "replies",
        "clicks",
        "purchases",
        "setup_requests",
        "feedback_themes",
        "objections",
        "buyer_language",
        "next_action",
    ]
    if fmt == "csv":
        return ",".join(columns)
    return "\n".join(
        [
            "| " + " | ".join(columns) + " |",
            "| " + " | ".join("---" for _ in columns) + " |",
            "|  |  |  |  |  |  |  |  |  |  |  |  |  |",
        ]
    )


def _load_market_log_entries(path: str) -> list[MarketLogEntry]:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if file_path.suffix.lower() == ".jsonl":
        return [
            MarketLogEntry.from_mapping(json.loads(line))
            for line in text.splitlines()
            if line.strip()
        ]
    if file_path.suffix.lower() == ".json":
        payload = json.loads(text)
        rows = payload.get("entries", payload) if isinstance(payload, dict) else payload
        return [MarketLogEntry.from_mapping(row) for row in rows]
    if file_path.suffix.lower() == ".csv":
        return [MarketLogEntry.from_mapping(row) for row in csv.DictReader(io.StringIO(text))]
    if file_path.suffix.lower() in {".md", ".txt"}:
        return _load_markdown_market_log(text)
    raise ValueError("Market log input must be .jsonl, .json, .csv, .md, or .txt.")


def _load_markdown_market_log(text: str) -> list[MarketLogEntry]:
    rows: list[MarketLogEntry] = []
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    if len(lines) < 3:
        return rows
    headers = [part.strip() for part in lines[0].strip("|").split("|")]
    for line in lines[2:]:
        values = [part.strip() for part in line.strip("|").split("|")]
        if len(values) != len(headers) or not any(values):
            continue
        rows.append(MarketLogEntry.from_mapping(dict(zip(headers, values))))
    return rows


def _refresh_item_safety(path: str, *, posting_only: bool = False) -> WorkflowContentItem:
    item = load_content_item(path)
    recent_items = [candidate for candidate in load_recent_content_items() if candidate.id != item.id]
    safety_layer = AstraSafetyLayer()
    refreshed = safety_layer.apply_to_item(
        item,
        recent_items=recent_items if posting_only or item.status in {"approved", "queued", "posted"} else None,
        rewrite_attempts=item.safety.rewrite_attempts,
    )
    write_content_item(path, refreshed)
    return refreshed


def _format_safety_summary(item: WorkflowContentItem) -> str:
    reasons = "; ".join(item.safety.reasons[:2]) if item.safety.reasons else "aligned"
    return f"Safety {item.safety.decision} | {item.id} | {item.topic} | {reasons}"

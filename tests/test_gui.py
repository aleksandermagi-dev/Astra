from __future__ import annotations

from astra.gui import (
    batch_args,
    campaign_args,
    conversational_args,
    format_latest_args,
    format_item_inspector,
    ideas_args,
    item_action_state,
    item_summary_rows,
    load_dashboard_items,
    market_log_args,
    accounts_status_args,
    approve_item_args,
    queue_item_args,
    mark_posted_args,
    publish_item_args,
    publish_log_args,
    publish_queue_args,
    posts_args,
    product_names,
    replies_args,
    review_drafts_args,
    review_queue_args,
    run_cli_capture,
    settings_status_lines,
    tendril_list_args,
)
from astra.config import AstraConfig
from astra.models import WorkflowContentItem
from astra.outputs import ensure_output_dirs, save_content_item


def test_gui_conversational_args_requires_text() -> None:
    try:
        conversational_args("  ")
    except ValueError as exc:
        assert "Type a request first" in str(exc)
    else:
        raise AssertionError("Expected blank conversational request to fail.")


def test_gui_conversational_args_wraps_request() -> None:
    assert conversational_args("draft 5 Reddit posts") == ["draft 5 Reddit posts"]


def test_gui_quick_action_args() -> None:
    assert ideas_args(topic="Continuity Layer", channel="reddit", count=3) == [
        "ideas",
        "--count",
        "3",
        "--platform",
        "reddit",
        "--topic",
        "Continuity Layer",
    ]
    assert batch_args(topic="Launch", count=7) == ["batch", "--topic", "Launch", "--count", "7", "--format", "md"]
    assert format_latest_args("hacker_news") == ["format", "the", "latest", "batch", "for", "hacker news"]
    assert market_log_args() == ["market-log-template", "--format", "md"]
    assert market_log_args(save=True) == ["market-log-template", "--format", "md", "--save"]
    assert tendril_list_args() == ["tendril", "list"]
    assert review_drafts_args() == ["review-drafts"]
    assert review_queue_args() == ["review-queue"]
    assert approve_item_args(r"C:\draft.json") == ["approve", "--input", r"C:\draft.json"]
    assert queue_item_args(r"C:\approved.json", "morning") == ["queue", "--input", r"C:\approved.json", "--slot", "morning"]
    assert mark_posted_args("abc12345") == ["mark-posted", "--id", "abc12345"]
    assert accounts_status_args() == ["accounts", "status"]
    assert publish_queue_args("bluesky") == ["publish-queue", "--platform", "bluesky"]
    assert publish_log_args() == ["publish-log"]
    assert publish_item_args("abc12345") == ["publish", "--id", "abc12345"]
    assert publish_item_args(r"C:\queued\item.json") == ["publish", "--input", r"C:\queued\item.json"]


def test_gui_pr_action_args() -> None:
    assert product_names(config=AstraConfig()) == ["company", "Continuity Layer"]
    assert campaign_args(product="Continuity Layer", goal="Launch") == [
        "campaign",
        "create",
        "--goal",
        "Launch",
        "--days",
        "7",
        "--product",
        "Continuity Layer",
    ]
    assert posts_args(product="Continuity Layer", channel="reddit", count=3, goal="Launch") == [
        "posts",
        "draft",
        "--channel",
        "reddit",
        "--count",
        "3",
        "--product",
        "Continuity Layer",
        "--goal",
        "Launch",
    ]
    assert replies_args(product="Continuity Layer", scenario="skeptical_user", user_signal="Is this just Notion?") == [
        "replies",
        "draft",
        "--scenario",
        "skeptical_user",
        "--product",
        "Continuity Layer",
        "--user-signal",
        "Is this just Notion?",
    ]


def test_gui_batch_args_requires_topic() -> None:
    try:
        batch_args(topic="", count=3)
    except ValueError as exc:
        assert "Topic is required" in str(exc)
    else:
        raise AssertionError("Expected blank batch topic to fail.")


def test_gui_run_cli_capture_collects_stdout_and_stderr() -> None:
    def fake_runner(argv, *, stdout, stderr):
        stdout.write(f"args={argv}")
        stderr.write("warning")
        return 2

    result = run_cli_capture(["market-log-template"], cli_runner=fake_runner)

    assert result.exit_code == 2
    assert result.output == "args=['market-log-template']"
    assert result.error == "warning"
    assert "warning" in result.display_text


def test_gui_run_cli_capture_handles_exceptions() -> None:
    def fake_runner(argv, *, stdout, stderr):
        raise RuntimeError("boom")

    result = run_cli_capture(["tendril", "list"], cli_runner=fake_runner)

    assert result.exit_code == 1
    assert result.error == "boom"


def _item(**overrides) -> WorkflowContentItem:
    payload = {
        "id": "item1234",
        "topic": "Continuity Layer",
        "hook": "Stop re-explaining your project to AI.",
        "script_lines": ["Agents need current project context.", "Continuity Layer keeps that local and reviewable."],
        "caption": "Early access is open.",
        "hashtags": ["#ai"],
        "platform": "x_bluesky",
        "suggested_post_time": "afternoon",
        "status": "draft",
        "created_at": "2026-05-22T12:00:00Z",
        "workflow_stage": "platform_variant",
        "source_item_id": "root1234",
        "platform_notes": "Track replies and objections.",
        "retention_check": "The pain is clear immediately.",
    }
    payload.update(overrides)
    return WorkflowContentItem.from_mapping(payload)


def test_dashboard_item_loading_and_rows(tmp_path) -> None:
    dirs = ensure_output_dirs(tmp_path / "outputs")
    save_content_item(_item(id="draft111"), dirs["batches"] / "batch_1")
    save_content_item(_item(id="queue111", status="queued"), dirs["queue"])

    drafts = load_dashboard_items("drafts", base_dir=tmp_path / "outputs")
    queue = item_summary_rows("queue", base_dir=tmp_path / "outputs")

    assert [item.item_id for item in drafts] == ["draft111"]
    assert queue[0][0] == "queue111"
    assert queue[0][1] == "x_bluesky"


def test_item_inspector_and_action_state(tmp_path) -> None:
    dirs = ensure_output_dirs(tmp_path / "outputs")
    draft_path = save_content_item(_item(id="draft111"), dirs["batches"] / "batch_1")
    approved_path = save_content_item(_item(id="appr1111", status="approved"), dirs["approved"])
    queued_path = save_content_item(_item(id="queue111", status="queued"), dirs["queue"])
    posted_path = save_content_item(_item(id="post1111", status="posted"), dirs["posted"])

    details = format_item_inspector(draft_path)

    assert "Stop re-explaining your project to AI." in details
    assert "Safety: PASS" in details
    assert item_action_state(draft_path)["approve"] is True
    assert item_action_state(draft_path)["publish"] is False
    assert item_action_state(approved_path)["queue"] is True
    assert item_action_state(queued_path)["publish"] is True
    assert item_action_state(posted_path)["mark_posted"] is False


def test_settings_status_lines_do_not_expose_secrets() -> None:
    config = AstraConfig(api_key="secret", bluesky_posting=AstraConfig().bluesky_posting)
    lines = settings_status_lines(config)

    assert any("OpenAI API key: configured" in line for line in lines)
    assert "secret" not in "\n".join(lines)

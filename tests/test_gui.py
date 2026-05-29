from __future__ import annotations

from astra.gui import (
    batch_args,
    campaign_args,
    clear_review_drafts_args,
    conversational_args,
    continuity_launch_pack_commands,
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
    busy_button_state,
    copy_to_clipboard,
    mark_posted_args,
    describe_launch_pack_command,
    launch_pack_progress_messages,
    paste_clipboard_into_text,
    publish_item_args,
    publish_log_args,
    publish_queue_args,
    posts_args,
    product_names,
    queue_status_text,
    replies_args,
    review_drafts_args,
    review_queue_args,
    run_cli_capture,
    run_launch_pack_commands,
    select_all_text,
    settings_status_lines,
    tendril_list_args,
    text_widget_content,
)
from astra.config import AstraConfig
from astra.models import WorkflowContentItem
from astra.outputs import approve_content_item, ensure_output_dirs, queue_content_item, save_content_item


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
    assert clear_review_drafts_args() == ["clear-review-drafts"]
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


def test_continuity_launch_pack_commands_are_exact_and_ordered() -> None:
    commands = continuity_launch_pack_commands()

    assert commands == [
        [
            "campaign",
            "create",
            "--goal",
            "Launch paid early access for Continuity Layer",
            "--days",
            "7",
            "--product",
            "Continuity Layer",
        ],
        [
            "posts",
            "draft",
            "--channel",
            "x_bluesky",
            "--count",
            "3",
            "--product",
            "Continuity Layer",
            "--goal",
            "Launch paid early access for Continuity Layer",
        ],
        [
            "posts",
            "draft",
            "--channel",
            "reddit",
            "--count",
            "2",
            "--product",
            "Continuity Layer",
            "--goal",
            "Launch paid early access for Continuity Layer",
        ],
        [
            "posts",
            "draft",
            "--channel",
            "hacker_news",
            "--count",
            "1",
            "--product",
            "Continuity Layer",
            "--goal",
            "Show HN / technical launch for Continuity Layer",
        ],
        [
            "posts",
            "draft",
            "--channel",
            "indie_hackers",
            "--count",
            "1",
            "--product",
            "Continuity Layer",
            "--goal",
            "Founder-built early access launch",
        ],
        ["replies", "draft", "--scenario", "skeptical_user", "--product", "Continuity Layer"],
        ["replies", "draft", "--scenario", "why_not_readme_notion", "--product", "Continuity Layer"],
        ["market-log-template", "--format", "md", "--save"],
    ]


def test_launch_pack_progress_messages_are_ordered() -> None:
    messages = launch_pack_progress_messages()

    assert messages == [
        "Step 1/8: creating 7-day campaign plan",
        "Step 2/8: drafting Bluesky posts",
        "Step 3/8: drafting Reddit posts",
        "Step 4/8: drafting Hacker News draft",
        "Step 5/8: drafting Indie Hackers draft",
        "Step 6/8: drafting skeptical-user reply",
        "Step 7/8: drafting README/Notion reply",
        "Step 8/8: saving market log template",
    ]
    assert describe_launch_pack_command(["unknown"]) == "running Astra command"


def test_run_launch_pack_commands_summarizes_success() -> None:
    calls = []
    progress = []

    def fake_runner(argv, *, stdout, stderr):
        calls.append(argv)
        stdout.write(f"saved {' '.join(argv[:2])}")
        return 0

    result = run_launch_pack_commands(cli_runner=fake_runner, progress_callback=progress.append)

    assert result.ok is True
    assert calls == continuity_launch_pack_commands()
    assert progress == launch_pack_progress_messages()
    assert "Launch pack created as drafts" in result.display_text
    assert "OK: campaign create" in result.display_text


def test_run_launch_pack_commands_summarizes_partial_failure() -> None:
    def fake_runner(argv, *, stdout, stderr):
        if argv[:2] == ["posts", "draft"] and "reddit" in argv:
            stderr.write("missing OPENAI_API_KEY")
            return 1
        stdout.write("ok")
        return 0

    result = run_launch_pack_commands(cli_runner=fake_runner)

    assert result.ok is False
    assert "FAILED (reddit drafts failed): posts draft" in result.display_text
    assert "missing OPENAI_API_KEY" in result.display_text
    assert "Saved drafts may still exist from later successful steps" in result.display_text
    assert "No approval, queue, or publish action was run" in result.display_text


def test_run_launch_pack_commands_names_campaign_failure_and_later_success() -> None:
    def fake_runner(argv, *, stdout, stderr):
        if argv[:2] == ["campaign", "create"]:
            stderr.write("Ollama is running, but this request took too long")
            return 1
        stdout.write("saved later step")
        return 0

    result = run_launch_pack_commands(cli_runner=fake_runner)

    assert result.ok is False
    assert "1. FAILED (campaign failed): campaign create" in result.display_text
    assert "2. OK: posts draft" in result.display_text
    assert "Ollama is running, but this request took too long" in result.display_text


def test_busy_button_state_maps_to_tk_states() -> None:
    assert busy_button_state(True) == "disabled"
    assert busy_button_state(False) == "normal"


class _FakeRoot:
    def __init__(self, clipboard: str = "") -> None:
        self.clipboard = clipboard

    def clipboard_clear(self) -> None:
        self.clipboard = ""

    def clipboard_append(self, text: str) -> None:
        self.clipboard += text

    def clipboard_get(self) -> str:
        return self.clipboard


class _FakeText:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.tags = []
        self.insert_mark = ""
        self.seen = ""

    def get(self, start: str, end: str) -> str:
        assert (start, end) == ("1.0", "end-1c")
        return self.text

    def insert(self, index: str, value: str) -> None:
        assert index == "insert"
        self.text += value

    def tag_add(self, tag: str, start: str, end: str) -> None:
        self.tags.append((tag, start, end))

    def mark_set(self, mark: str, index: str) -> None:
        self.insert_mark = f"{mark}:{index}"

    def see(self, index: str) -> None:
        self.seen = index


def test_clipboard_helpers_copy_paste_and_select_all() -> None:
    root = _FakeRoot(" pasted")
    widget = _FakeText("hello")

    assert text_widget_content(widget) == "hello"
    assert copy_to_clipboard(root, "copied") == "copied"
    assert root.clipboard == "copied"
    root.clipboard = " pasted"
    assert paste_clipboard_into_text(widget, root) == " pasted"
    assert widget.text == "hello pasted"
    assert select_all_text(widget) == "break"
    assert ("sel", "1.0", "end-1c") in widget.tags


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
    save_content_item(_item(id="appr1111", status="approved"), dirs["approved"])
    save_content_item(_item(id="queue111", status="queued"), dirs["queue"])

    drafts = load_dashboard_items("drafts", base_dir=tmp_path / "outputs")
    queue_items = load_dashboard_items("queue", base_dir=tmp_path / "outputs")
    queue = item_summary_rows("queue", base_dir=tmp_path / "outputs")

    assert [item.item_id for item in drafts] == ["draft111"]
    assert [item.item_id for item in queue_items] == ["appr1111", "queue111"]
    assert [(row[0], row[2]) for row in queue] == [("appr1111", "approved"), ("queue111", "queued")]
    assert queue[0][1] == "x_bluesky"
    assert queue_status_text(base_dir=tmp_path / "outputs") == "Queue: 1 queued / 1 approved"


def test_approved_item_appears_in_queue_dashboard_until_it_is_queued(tmp_path) -> None:
    dirs = ensure_output_dirs(tmp_path / "outputs")
    draft_path = save_content_item(_item(id="draft111"), dirs["batches"] / "batch_1")

    approved_path = approve_content_item(draft_path, base_dir=tmp_path / "outputs")

    approved_queue_items = load_dashboard_items("queue", base_dir=tmp_path / "outputs")
    assert [(item.item_id, item.status, item.path) for item in approved_queue_items] == [
        ("draft111", "approved", approved_path)
    ]

    queued_path = queue_content_item(approved_path, base_dir=tmp_path / "outputs")

    queued_dashboard_items = load_dashboard_items("queue", base_dir=tmp_path / "outputs")
    assert [(item.item_id, item.status, item.path) for item in queued_dashboard_items] == [
        ("draft111", "queued", queued_path)
    ]


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

    assert any("Generation provider: openai" in line for line in lines)
    assert any("Generation model: gpt-5-mini" in line for line in lines)
    assert any("OpenAI API key: configured" in line for line in lines)
    assert "secret" not in "\n".join(lines)


def test_settings_status_lines_include_bluesky_restart_guidance() -> None:
    lines = settings_status_lines(AstraConfig(), diagnostics_func=lambda **_: ["Ollama diagnostic skipped."])

    assert any("restart Astra" in line for line in lines)
    assert "Ollama diagnostic skipped." in lines

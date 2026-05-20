from __future__ import annotations

from astra.gui import (
    batch_args,
    campaign_args,
    conversational_args,
    format_latest_args,
    ideas_args,
    market_log_args,
    posts_args,
    product_names,
    replies_args,
    review_drafts_args,
    review_queue_args,
    run_cli_capture,
    tendril_list_args,
)
from astra.config import AstraConfig


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

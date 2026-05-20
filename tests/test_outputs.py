from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

from astra import outputs
from astra.models import AnalyticsLogEntry, WorkflowContentItem
from astra.outputs import (
    append_analytics_log,
    approve_content_item,
    build_timestamped_filename,
    create_ready_output_dir,
    ensure_output_dirs,
    mark_content_item_posted,
    queue_content_item,
    resolve_queue_timestamp,
    save_content_item,
    save_generated_output,
    slugify_topic,
    write_content_item,
)


def _sample_item(**overrides) -> WorkflowContentItem:
    payload = {
        "id": "item1234",
        "topic": "AI myths",
        "hook": "AI panic is easy to sell",
        "script_lines": ["line one", "line two"],
        "caption": "caption",
        "hashtags": ["#ai"],
        "platform": "master",
        "suggested_post_time": "afternoon",
        "status": "draft",
        "created_at": "2026-03-29T12:00:00Z",
        "workflow_stage": "master",
        "retention_check": "One sentence only",
    }
    payload.update(overrides)
    return WorkflowContentItem.from_mapping(payload)


def test_ensure_output_dirs_creates_expected_structure(tmp_path) -> None:
    directories = ensure_output_dirs(tmp_path / "outputs")
    assert directories["ideas"].is_dir()
    assert directories["campaigns"].is_dir()
    assert directories["batches"].is_dir()
    assert directories["replies"].is_dir()
    assert directories["feedback"].is_dir()
    assert directories["experiments"].is_dir()
    assert directories["queue"].is_dir()
    assert directories["approved"].is_dir()
    assert directories["posted"].is_dir()
    assert directories["logs"].is_dir()
    assert directories["ready"].is_dir()


def test_slugify_topic_handles_spaces_and_punctuation() -> None:
    assert slugify_topic("AI myths?! 2026") == "ai_myths_2026"
    assert slugify_topic("   ") == "untitled"


def test_build_timestamped_filename_uses_expected_pattern() -> None:
    name = build_timestamped_filename(
        topic="AI myths",
        suffix="ideas",
        now=datetime(2026, 3, 30, 9, 0, 0),
    )
    assert name == "2026-03-30_ai_myths_ideas.txt"


def test_save_generated_output_writes_to_expected_folder(tmp_path) -> None:
    target = save_generated_output(
        content="hello",
        topic="AI myths",
        kind="ideas",
        base_dir=tmp_path / "outputs",
        now=datetime(2026, 3, 30, 9, 0, 0),
    )
    assert target.name == "2026-03-30_ai_myths_ideas.txt"
    assert target.read_text(encoding="utf-8") == "hello"
    assert target.parent.name == "ideas"


def test_default_outputs_root_uses_executable_directory_when_frozen(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\Astra\Astra.exe")

    assert outputs.default_outputs_root() == Path(r"C:\Apps\Astra\outputs")


def test_save_approve_queue_and_post_workflow_item(tmp_path) -> None:
    dirs = ensure_output_dirs(tmp_path / "outputs")
    draft_path = save_content_item(_sample_item(), dirs["batches"])

    approved_path = approve_content_item(draft_path, base_dir=tmp_path / "outputs")
    approved_item = outputs.load_content_item(approved_path)
    assert approved_item.status == "approved"
    assert approved_path.parent.name == "approved"

    queued_path = queue_content_item(approved_path, base_dir=tmp_path / "outputs", now=datetime(2026, 3, 29, 8, 0, 0))
    queued_item = outputs.load_content_item(queued_path)
    assert queued_item.status == "queued"
    assert queued_path.parent.name == "queue"
    assert queued_item.suggested_post_time == "2026-03-29T13:00"

    posted_path = mark_content_item_posted(queued_path, base_dir=tmp_path / "outputs")
    posted_item = outputs.load_content_item(posted_path)
    assert posted_item.status == "posted"
    assert posted_path.parent.name == "posted"


def test_append_analytics_log_writes_jsonl(tmp_path) -> None:
    entry = AnalyticsLogEntry(
        platform="tiktok",
        topic="AI myths",
        date_posted="2026-03-29",
        post_id_or_url="https://example.com/post/123",
        views=1000,
        likes=50,
        comments=4,
        notes="Strong hook",
    )
    target = append_analytics_log(entry, base_dir=tmp_path / "outputs", now=datetime(2026, 3, 29, 10, 0, 0))

    assert target.name == "2026-03-29_analytics.jsonl"
    assert '"platform": "tiktok"' in target.read_text(encoding="utf-8")


def test_resolve_queue_timestamp_supports_slots() -> None:
    assert resolve_queue_timestamp("morning", now=datetime(2026, 3, 29, 8, 0, 0)) == "2026-03-29T09:00"


def test_create_ready_output_dir_uses_timestamp_topic_and_id(tmp_path) -> None:
    item = _sample_item(id="abcd1234", topic="Why people trust you fast?")

    target = create_ready_output_dir(
        item,
        base_dir=tmp_path / "outputs",
        now=datetime(2026, 3, 30, 16, 45, 0),
    )

    assert target.name == "20260330_164500_why_people_trust_you_fast_abcd1234"
    assert target.parent.name == "ready"


def test_review_draft_items_excludes_discarded_content(tmp_path) -> None:
    dirs = ensure_output_dirs(tmp_path / "outputs")
    batch_dir = dirs["batches"] / "batch_20260330_120000"
    save_content_item(_sample_item(id="pass1234"), batch_dir)
    save_content_item(
        _sample_item(
            id="drop1234",
            safety={
                "decision": "DISCARD",
                "dimension_results": {"topic": "DISCARD"},
                "reasons": ["Unsafe topic."],
                "scores": {},
                "rewrite_attempts": 1,
                "last_evaluated_at": "2026-03-30T12:00:00Z",
            },
        ),
        batch_dir,
    )

    reviewed = outputs.review_draft_items(tmp_path / "outputs")

    assert [item.id for item in reviewed] == ["pass1234"]

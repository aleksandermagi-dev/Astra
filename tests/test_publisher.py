from __future__ import annotations

import json
from pathlib import Path

from astra.config import AstraConfig, BlueskyPostingConfig
from astra.models import WorkflowContentItem
from astra.outputs import ensure_output_dirs, load_content_item, save_content_item
from astra.publisher import BlueskyPublisher, PublisherError, PublishingService, workflow_item_to_bluesky_text


def _item(**overrides) -> WorkflowContentItem:
    payload = {
        "id": "bsky1234",
        "topic": "Continuity Layer",
        "hook": "Stop re-explaining your project to AI.",
        "script_lines": ["Continuity Layer keeps local project memory for agents."],
        "caption": "Early access is open.",
        "hashtags": ["#AI"],
        "platform": "x_bluesky",
        "suggested_post_time": "afternoon",
        "status": "queued",
        "created_at": "2026-05-22T12:00:00Z",
        "workflow_stage": "platform_variant",
        "source_item_id": "root1234",
        "platform_notes": "Track replies and objections.",
        "retention_check": "The pain is clear immediately.",
    }
    payload.update(overrides)
    return WorkflowContentItem.from_mapping(payload)


def test_bluesky_publisher_builds_expected_api_requests() -> None:
    calls = []

    def fake_transport(url, payload, *, headers=None):
        calls.append((url, payload, headers or {}))
        if url.endswith("createSession"):
            return {"accessJwt": "token", "did": "did:plc:test"}
        return {"uri": "at://did:plc:test/app.bsky.feed.post/abc123", "cid": "cid123"}

    publisher = BlueskyPublisher(
        BlueskyPostingConfig(handle="linnutee.bsky.social", app_password="app-pass"),
        transport=fake_transport,
    )

    result = publisher.publish(_item())

    assert result.status == "posted"
    assert result.external_id.startswith("at://")
    assert result.external_url == "https://bsky.app/profile/linnutee.bsky.social/post/abc123"
    assert calls[0][0].endswith("/xrpc/com.atproto.server.createSession")
    assert calls[0][1] == {"identifier": "linnutee.bsky.social", "password": "app-pass"}
    assert calls[1][0].endswith("/xrpc/com.atproto.repo.createRecord")
    assert calls[1][1]["collection"] == "app.bsky.feed.post"
    assert calls[1][1]["record"]["$type"] == "app.bsky.feed.post"
    assert calls[1][2]["Authorization"] == "Bearer token"


def test_bluesky_publisher_rejects_non_queued_items_and_long_text() -> None:
    publisher = BlueskyPublisher(BlueskyPostingConfig(handle="x", app_password="y"), transport=lambda *_, **__: {})

    for status in ("draft", "approved"):
        try:
            publisher.publish(_item(status=status))
        except PublisherError as exc:
            assert "Only queued" in str(exc)
        else:
            raise AssertionError(f"{status} item should not publish.")

    try:
        publisher.publish(_item(hook="x" * 301))
    except PublisherError as exc:
        assert "too long" in str(exc)
    else:
        raise AssertionError("Overlong Bluesky item should not publish.")


def test_missing_credentials_logs_failure_and_does_not_move_item(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    dirs = ensure_output_dirs(tmp_path / "outputs")
    path = save_content_item(_item(), dirs["queue"])
    service = PublishingService(AstraConfig(bluesky_posting=BlueskyPostingConfig()))

    result = service.publish_path(path)

    assert result.status == "failed"
    assert path.exists()
    assert load_content_item(path).status == "queued"
    logs = list((tmp_path / "outputs" / "logs").glob("*_publish.jsonl"))
    assert logs
    assert "ASTRA_BLUESKY_HANDLE" in logs[0].read_text(encoding="utf-8")


def test_successful_publish_moves_item_to_posted_and_writes_log(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    dirs = ensure_output_dirs(tmp_path / "outputs")
    path = save_content_item(_item(), dirs["queue"])

    def fake_transport(url, payload, *, headers=None):
        if url.endswith("createSession"):
            return {"accessJwt": "token", "did": "did:plc:test"}
        return {"uri": "at://did:plc:test/app.bsky.feed.post/rkey123", "cid": "cid123"}

    service = PublishingService(
        AstraConfig(bluesky_posting=BlueskyPostingConfig(handle="linnutee.bsky.social", app_password="app-pass")),
        bluesky_transport=fake_transport,
    )

    result = service.publish_path(path)

    assert result.status == "posted"
    assert not path.exists()
    posted = list((tmp_path / "outputs" / "posted").glob("*_posted_*.json"))
    assert posted
    assert json.loads(posted[0].read_text(encoding="utf-8"))["status"] == "posted"
    logs = list((tmp_path / "outputs" / "logs").glob("*_publish.jsonl"))
    assert "https://bsky.app/profile/linnutee.bsky.social/post/rkey123" in logs[0].read_text(encoding="utf-8")


def test_publish_queue_only_attempts_bluesky_items(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    dirs = ensure_output_dirs(tmp_path / "outputs")
    save_content_item(_item(id="bsky1111", platform="x_bluesky"), dirs["queue"])
    save_content_item(_item(id="red11111", platform="reddit"), dirs["queue"])
    calls = []

    def fake_transport(url, payload, *, headers=None):
        calls.append(url)
        if url.endswith("createSession"):
            return {"accessJwt": "token", "did": "did:plc:test"}
        return {"uri": "at://did:plc:test/app.bsky.feed.post/rkey123", "cid": "cid123"}

    service = PublishingService(
        AstraConfig(bluesky_posting=BlueskyPostingConfig(handle="linnutee.bsky.social", app_password="app-pass")),
        bluesky_transport=fake_transport,
    )

    results = service.publish_queue("bluesky")

    assert [result.item_id for result in results] == ["bsky1111"]
    assert len(calls) == 2
    assert (tmp_path / "outputs" / "queue" / "2026-05-22_continuity_layer_reddit_queued_red11111.json").exists()


def test_workflow_item_to_bluesky_text_includes_hashtags() -> None:
    assert workflow_item_to_bluesky_text(_item()).endswith("#AI")

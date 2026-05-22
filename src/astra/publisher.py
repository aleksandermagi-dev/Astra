from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol
from urllib import request

from .config import AstraConfig, BlueskyPostingConfig
from .models import PublishResult, WorkflowContentItem
from .outputs import (
    append_publish_log,
    find_content_item_path,
    load_content_item,
    move_content_item,
    review_queue_items,
)


class PublisherError(ValueError):
    pass


class JsonTransport(Protocol):
    def __call__(self, url: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> dict[str, Any]: ...


def post_json(url: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def workflow_item_to_bluesky_text(item: WorkflowContentItem) -> str:
    parts = [item.hook, *item.script_lines, item.caption]
    text = "\n\n".join(part.strip() for part in parts if part.strip())
    tags = " ".join(tag for tag in item.hashtags if tag.strip())
    if tags:
        text = f"{text}\n\n{tags}"
    return text.strip()


def validate_bluesky_text(text: str) -> None:
    if not text:
        raise PublisherError("Bluesky post text cannot be empty.")
    if len(text) > 300:
        raise PublisherError(f"Bluesky post is too long: {len(text)}/300 characters.")


def bluesky_url_from_uri(uri: str, handle: str) -> str:
    rkey = uri.rstrip("/").split("/")[-1]
    return f"https://bsky.app/profile/{handle}/post/{rkey}" if rkey else ""


class BlueskyPublisher:
    platform = "bluesky"

    def __init__(
        self,
        config: BlueskyPostingConfig,
        *,
        transport: JsonTransport = post_json,
    ) -> None:
        self.config = config
        self.transport = transport

    def account_status(self) -> str:
        return "configured" if self.config.configured else "missing_credentials"

    def publish(self, item: WorkflowContentItem) -> PublishResult:
        if item.status not in {"approved", "queued"}:
            raise PublisherError("Only approved or queued items can be published.")
        if item.platform not in {"x_bluesky", "bluesky"}:
            raise PublisherError("Bluesky publisher only supports x_bluesky/bluesky items.")
        if not self.config.configured:
            raise PublisherError("ASTRA_BLUESKY_HANDLE and ASTRA_BLUESKY_APP_PASSWORD are required.")

        text = workflow_item_to_bluesky_text(item)
        validate_bluesky_text(text)

        session = self.transport(
            f"{self.config.service_url}/xrpc/com.atproto.server.createSession",
            {"identifier": self.config.handle, "password": self.config.app_password},
        )
        access_jwt = str(session.get("accessJwt") or "")
        did = str(session.get("did") or session.get("handle") or self.config.handle)
        if not access_jwt:
            raise PublisherError("Bluesky session did not return an access token.")

        record = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": item.created_at,
        }
        created = self.transport(
            f"{self.config.service_url}/xrpc/com.atproto.repo.createRecord",
            {
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": record,
            },
            headers={"Authorization": f"Bearer {access_jwt}"},
        )
        uri = str(created.get("uri") or "")
        cid = str(created.get("cid") or "")
        return PublishResult(
            platform=self.platform,
            item_id=item.id,
            status="posted",
            external_id=uri or cid,
            external_url=bluesky_url_from_uri(uri, self.config.handle),
            account_label=self.config.account_label,
        )


class PublishingService:
    def __init__(
        self,
        config: AstraConfig | None = None,
        *,
        bluesky_transport: JsonTransport = post_json,
    ) -> None:
        self.config = config or AstraConfig.load()
        self.bluesky = BlueskyPublisher(self.config.bluesky_posting, transport=bluesky_transport)

    def accounts_status(self) -> dict[str, str]:
        return {"bluesky": self.bluesky.account_status()}

    def publish_path(self, path: str | Path) -> PublishResult:
        item_path = Path(path)
        item = load_content_item(item_path)
        try:
            result = self._publisher_for_item(item).publish(item)
        except Exception as exc:
            result = PublishResult(
                platform=self._platform_for_item(item),
                item_id=item.id,
                status="failed",
                account_label=self.config.bluesky_posting.account_label,
                error=str(exc),
            )
            append_publish_log(result)
            return result
        append_publish_log(result)
        move_content_item(item_path, destination_kind="posted", status="posted")
        return result

    def publish_id(self, item_id: str) -> PublishResult:
        return self.publish_path(find_content_item_path(item_id))

    def publish_queue(self, platform: str = "bluesky") -> list[PublishResult]:
        normalized = _normalize_publish_platform(platform)
        results: list[PublishResult] = []
        for item in review_queue_items():
            if self._platform_for_item(item) != normalized:
                continue
            results.append(self.publish_id(item.id))
        return results

    def _publisher_for_item(self, item: WorkflowContentItem) -> BlueskyPublisher:
        platform = self._platform_for_item(item)
        if platform == "bluesky":
            return self.bluesky
        raise PublisherError(f"No publisher configured for platform: {item.platform}")

    def _platform_for_item(self, item: WorkflowContentItem) -> str:
        return _normalize_publish_platform(item.platform)


def _normalize_publish_platform(platform: str) -> str:
    normalized = platform.strip().lower()
    if normalized in {"bluesky", "x_bluesky", "x/bluesky"}:
        return "bluesky"
    return normalized

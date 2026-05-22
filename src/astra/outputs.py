from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import sys
from typing import Iterable

from .models import AnalyticsLogEntry, PublishResult, VALID_POST_TIME_SLOTS, WorkflowContentItem


WORKFLOW_DIRECTORIES = (
    "ideas",
    "campaigns",
    "batches",
    "replies",
    "feedback",
    "experiments",
    "queue",
    "approved",
    "posted",
    "logs",
    "ready",
)
SLOT_HOURS = {
    "morning": 9,
    "afternoon": 13,
    "evening": 18,
}


def default_outputs_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "outputs"
    return Path(__file__).resolve().parents[2] / "outputs"


def ensure_output_dirs(base_dir: Path | None = None) -> dict[str, Path]:
    root = base_dir or default_outputs_root()
    directories = {"root": root}
    for name in WORKFLOW_DIRECTORIES:
        directories[name] = root / name
    for path in directories.values():
        path.mkdir(parents=True, exist_ok=True)
    return directories


def slugify_topic(topic: str | None, fallback: str = "untitled") -> str:
    cleaned = (topic or "").strip().lower()
    if not cleaned:
        return fallback
    slug = re.sub(r"[^a-z0-9]+", "_", cleaned).strip("_")
    return slug or fallback


def build_timestamped_filename(
    *,
    topic: str | None,
    suffix: str,
    extension: str = "txt",
    now: datetime | None = None,
) -> str:
    current = now or datetime.now()
    date_prefix = current.strftime("%Y-%m-%d")
    slug = slugify_topic(topic)
    return f"{date_prefix}_{slug}_{suffix}.{extension}"


def save_generated_output(
    *,
    content: str,
    topic: str | None,
    kind: str,
    base_dir: Path | None = None,
    extension: str = "txt",
    now: datetime | None = None,
) -> Path:
    directories = ensure_output_dirs(base_dir)
    if kind not in {"ideas", "campaigns", "batches", "replies", "feedback", "experiments", "approved", "queue", "posted", "logs"}:
        raise ValueError("Unsupported output kind.")
    target = directories[kind] / build_timestamped_filename(
        topic=topic,
        suffix=_suffix_for_kind(kind),
        extension=extension,
        now=now,
    )
    target.write_text(content, encoding="utf-8")
    return target


def open_outputs_directory(base_dir: Path | None = None, *, kind: str = "root") -> Path:
    directories = ensure_output_dirs(base_dir)
    target = directories[kind]
    startfile = getattr(os, "startfile", None)
    if startfile is not None:
        try:
            startfile(str(target))
        except OSError:
            pass
    return target


def create_batch_run_dir(base_dir: Path | None = None, *, now: datetime | None = None) -> Path:
    directories = ensure_output_dirs(base_dir)
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    target = directories["batches"] / f"batch_{stamp}"
    target.mkdir(parents=True, exist_ok=True)
    return target


def create_ready_output_dir(
    item: WorkflowContentItem,
    base_dir: Path | None = None,
    *,
    now: datetime | None = None,
) -> Path:
    directories = ensure_output_dirs(base_dir)
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    slug = slugify_topic(item.topic)
    target = directories["ready"] / f"{stamp}_{slug}_{item.id}"
    target.mkdir(parents=True, exist_ok=True)
    return target


def save_content_item(item: WorkflowContentItem, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / build_content_item_filename(item)
    target.write_text(json.dumps(item.to_mapping(), indent=2), encoding="utf-8")
    return target


def write_content_item(path: str | Path, item: WorkflowContentItem) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(item.to_mapping(), indent=2), encoding="utf-8")
    return target


def save_batch_items(items: Iterable[WorkflowContentItem], batch_dir: Path) -> list[Path]:
    return [save_content_item(item, batch_dir) for item in items]


def load_content_item(path: str | Path) -> WorkflowContentItem:
    file_path = Path(path)
    return WorkflowContentItem.from_mapping(json.loads(file_path.read_text(encoding="utf-8")))


def load_content_items(path: str | Path) -> list[WorkflowContentItem]:
    file_path = Path(path)
    if file_path.is_dir():
        return [load_content_item(candidate) for candidate in sorted(file_path.glob("*.json"))]
    return [load_content_item(file_path)]


def build_content_item_filename(item: WorkflowContentItem) -> str:
    date_prefix = item.created_at[:10]
    slug = slugify_topic(item.topic)
    return f"{date_prefix}_{slug}_{item.platform}_{item.status}_{item.id}.json"


def move_content_item(
    path: str | Path,
    *,
    destination_kind: str,
    status: str,
    suggested_post_time: str | None = None,
    base_dir: Path | None = None,
) -> Path:
    source = Path(path)
    item = load_content_item(source)
    item = item.with_updates(
        status=status,
        suggested_post_time=suggested_post_time or item.suggested_post_time,
    )
    directories = ensure_output_dirs(base_dir)
    target_dir = directories[destination_kind]
    target_path = target_dir / build_content_item_filename(item)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(item.to_mapping(), indent=2), encoding="utf-8")
    if source.resolve() != target_path.resolve():
        source.unlink()
    return target_path


def approve_content_item(path: str | Path, base_dir: Path | None = None) -> Path:
    item = load_content_item(path)
    if item.safety.decision != "PASS":
        raise ValueError("Only safety PASS items can be approved.")
    return move_content_item(path, destination_kind="approved", status="approved", base_dir=base_dir)


def queue_content_item(
    path: str | Path,
    *,
    slot: str | None = None,
    base_dir: Path | None = None,
    now: datetime | None = None,
) -> Path:
    item = load_content_item(path)
    if item.status != "approved":
        raise ValueError("Only approved items can be queued.")
    if item.safety.decision != "PASS":
        raise ValueError("Only safety PASS items can be queued.")
    resolved = resolve_queue_timestamp(slot or item.suggested_post_time, now=now)
    return move_content_item(
        path,
        destination_kind="queue",
        status="queued",
        suggested_post_time=resolved,
        base_dir=base_dir,
    )


def mark_content_item_posted(path: str | Path, base_dir: Path | None = None) -> Path:
    item = load_content_item(path)
    if item.status != "queued":
        raise ValueError("Only queued items can be marked as posted.")
    return move_content_item(path, destination_kind="posted", status="posted", base_dir=base_dir)


def resolve_queue_timestamp(slot_or_timestamp: str, *, now: datetime | None = None) -> str:
    value = slot_or_timestamp.strip().lower()
    if value not in VALID_POST_TIME_SLOTS:
        return slot_or_timestamp
    current = now or datetime.now()
    target = current.replace(hour=SLOT_HOURS[value], minute=0, second=0, microsecond=0)
    if target <= current:
        target = target + timedelta(days=1)
    return target.isoformat(timespec="minutes")


def review_queue_items(base_dir: Path | None = None) -> list[WorkflowContentItem]:
    directories = ensure_output_dirs(base_dir)
    return [item for item in load_content_items(directories["queue"]) if item.safety.decision != "DISCARD"]


def review_draft_items(base_dir: Path | None = None) -> list[WorkflowContentItem]:
    directories = ensure_output_dirs(base_dir)
    items: list[WorkflowContentItem] = []
    for batch_dir in sorted(directories["batches"].glob("*")):
        if batch_dir.is_dir():
            items.extend(load_content_items(batch_dir))
    return [item for item in items if item.status == "draft" and item.safety.decision != "DISCARD"]


def load_recent_content_items(base_dir: Path | None = None, *, include_drafts: bool = False) -> list[WorkflowContentItem]:
    directories = ensure_output_dirs(base_dir)
    items: list[WorkflowContentItem] = []
    root_names = ("batches", "approved", "queue", "posted") if include_drafts else ("approved", "queue", "posted")
    for root_name in root_names:
        root = directories[root_name]
        if root_name == "batches":
            for batch_dir in sorted(root.glob("*")):
                if batch_dir.is_dir():
                    items.extend(load_content_items(batch_dir))
        else:
            items.extend(load_content_items(root))
    return items


def append_analytics_log(entry: AnalyticsLogEntry, base_dir: Path | None = None, *, now: datetime | None = None) -> Path:
    directories = ensure_output_dirs(base_dir)
    target = directories["logs"] / f"{(now or datetime.now()).strftime('%Y-%m-%d')}_analytics.jsonl"
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry.to_mapping()) + "\n")
    return target


def append_publish_log(result: PublishResult, base_dir: Path | None = None, *, now: datetime | None = None) -> Path:
    directories = ensure_output_dirs(base_dir)
    target = directories["logs"] / f"{(now or datetime.now()).strftime('%Y-%m-%d')}_publish.jsonl"
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result.to_mapping()) + "\n")
    return target


def load_publish_log(base_dir: Path | None = None) -> list[PublishResult]:
    directories = ensure_output_dirs(base_dir)
    results: list[PublishResult] = []
    for path in sorted(directories["logs"].glob("*_publish.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                results.append(PublishResult.from_mapping(json.loads(line)))
    return results


def find_content_item_path(item_id: str, base_dir: Path | None = None) -> Path:
    directories = ensure_output_dirs(base_dir)
    search_roots = [directories["batches"], directories["approved"], directories["queue"], directories["posted"]]
    for root in search_roots:
        for candidate in root.rglob(f"*_{item_id}.json"):
            return candidate
    raise FileNotFoundError(f"Could not find content item with id '{item_id}'.")


def _suffix_for_kind(kind: str) -> str:
    return {
        "ideas": "ideas",
        "campaigns": "campaign",
        "batches": "batch",
        "replies": "replies",
        "feedback": "feedback",
        "experiments": "experiments",
        "approved": "approved",
        "queue": "queue",
        "posted": "posted",
        "logs": "log",
    }[kind]

from __future__ import annotations

from collections import Counter
import csv
import json
from pathlib import Path

from .models import PerformanceRecord


def load_performance_records(path: str) -> list[PerformanceRecord]:
    file_path = Path(path)
    if file_path.suffix.lower() == ".csv":
        with file_path.open("r", encoding="utf-8", newline="") as handle:
            return [PerformanceRecord.from_mapping(row) for row in csv.DictReader(handle)]
    data = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("records", [])
    return [PerformanceRecord.from_mapping(item) for item in data]


def summarize_performance(records: list[PerformanceRecord]) -> str:
    if not records:
        return "No performance records found."

    top_views = max(records, key=lambda item: item.views or 0)
    top_retention = max(records, key=lambda item: item.retention or 0)
    platform_counts = Counter(record.platform for record in records)

    recommendations: list[str] = []
    if top_retention.retention is not None:
        recommendations.append(
            f"Best retention came from hook '{top_retention.hook}' on {top_retention.platform}."
        )
    recommendations.append(
        f"Most-viewed topic was '{top_views.topic}' with hook '{top_views.hook}'."
    )
    recommendations.append(
        f"Most-tested platform so far: {platform_counts.most_common(1)[0][0]}."
    )
    recommendations.append(
        "Prefer hooks that create immediate tension, keep scripts compressed, and retire flat educational openings."
    )
    return "\n".join(recommendations)

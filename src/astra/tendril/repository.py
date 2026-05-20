from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _json_loads(value: object, fallback: object) -> object:
    if value is None:
        return fallback
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return fallback


def _decode_row(row: sqlite3.Row | None, *, json_fields: tuple[str, ...] = ()) -> dict[str, object] | None:
    if row is None:
        return None
    payload = dict(row)
    for field in json_fields:
        if field in payload:
            payload[field] = _json_loads(payload.get(field), {} if field.endswith("_json") else None)
    return payload


class TendrilDatabase:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise


class TendrilRepository:
    TASK_JSON_FIELDS = ("required_tools_json", "completion_criteria_json", "metadata_json")
    PLAN_JSON_FIELDS = ("metadata_json",)
    STEP_JSON_FIELDS = ("inputs_json", "retry_policy_json", "changed_paths_json", "metadata_json")
    AUDIT_JSON_FIELDS = ("changed_paths_json", "reversal_conditions_json", "metadata_json")

    def __init__(self, database: TendrilDatabase):
        self.database = database

    def upsert_task(
        self,
        *,
        task_id: str,
        goal: str,
        intent_summary: str | None,
        risk_level: str,
        required_tools: list[str],
        status: str,
        approval_state: str,
        project_id: str | None,
        session_id: str | None,
        completion_criteria: list[str],
        archive_state: str,
        created_at: str,
        updated_at: str,
        approved_at: str | None = None,
        completed_at: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        with self.database.transaction() as conn:
            conn.execute(
                """
                INSERT INTO tendril_tasks (
                    id, goal, intent_summary, risk_level, required_tools_json, status,
                    approval_state, project_id, session_id, completion_criteria_json,
                    archive_state, created_at, updated_at, approved_at, completed_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    goal = excluded.goal,
                    intent_summary = excluded.intent_summary,
                    risk_level = excluded.risk_level,
                    required_tools_json = excluded.required_tools_json,
                    status = excluded.status,
                    approval_state = excluded.approval_state,
                    project_id = excluded.project_id,
                    session_id = excluded.session_id,
                    completion_criteria_json = excluded.completion_criteria_json,
                    archive_state = excluded.archive_state,
                    updated_at = excluded.updated_at,
                    approved_at = excluded.approved_at,
                    completed_at = excluded.completed_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    task_id,
                    goal,
                    intent_summary,
                    risk_level,
                    _json_dumps(required_tools),
                    status,
                    approval_state,
                    project_id,
                    session_id,
                    _json_dumps(completion_criteria),
                    archive_state,
                    created_at,
                    updated_at,
                    approved_at,
                    completed_at,
                    _json_dumps(metadata or {}),
                ),
            )
            row = conn.execute("SELECT * FROM tendril_tasks WHERE id = ?", (task_id,)).fetchone()
        return _decode_row(row, json_fields=self.TASK_JSON_FIELDS) or {}

    def get_task(self, task_id: str) -> dict[str, object] | None:
        with self.database.connect() as conn:
            row = conn.execute("SELECT * FROM tendril_tasks WHERE id = ?", (task_id,)).fetchone()
        return _decode_row(row, json_fields=self.TASK_JSON_FIELDS)

    def list_tasks(
        self,
        *,
        session_id: str | None = None,
        project_id: str | None = None,
        status: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        clauses: list[str] = []
        params: list[object] = []
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if not include_archived:
            clauses.append("archive_state != 'archived'")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(int(limit), 1))
        with self.database.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM tendril_tasks
                {where}
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [_decode_row(row, json_fields=self.TASK_JSON_FIELDS) or {} for row in rows]

    def upsert_plan(
        self,
        *,
        plan_id: str,
        task_id: str,
        version: int,
        status: str,
        planner_rationale: str | None,
        current_step_index: int,
        created_at: str,
        updated_at: str,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        with self.database.transaction() as conn:
            conn.execute(
                """
                INSERT INTO tendril_plans (
                    id, task_id, version, status, planner_rationale, current_step_index,
                    created_at, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    planner_rationale = excluded.planner_rationale,
                    current_step_index = excluded.current_step_index,
                    updated_at = excluded.updated_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    plan_id,
                    task_id,
                    version,
                    status,
                    planner_rationale,
                    current_step_index,
                    created_at,
                    updated_at,
                    _json_dumps(metadata or {}),
                ),
            )
            row = conn.execute("SELECT * FROM tendril_plans WHERE id = ?", (plan_id,)).fetchone()
        return _decode_row(row, json_fields=self.PLAN_JSON_FIELDS) or {}

    def latest_plan_for_task(self, task_id: str) -> dict[str, object] | None:
        with self.database.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM tendril_plans
                WHERE task_id = ?
                ORDER BY version DESC, created_at DESC, id DESC
                LIMIT 1
                """,
                (task_id,),
            ).fetchone()
        return _decode_row(row, json_fields=self.PLAN_JSON_FIELDS)

    def upsert_step(
        self,
        *,
        step_id: str,
        plan_id: str,
        task_id: str,
        step_index: int,
        action_type: str,
        required_tool: str | None,
        local_action: str | None,
        inputs: dict[str, object],
        expected_output: str | None,
        risk_level: str,
        approval_required: bool,
        retry_policy: dict[str, object],
        fallback_behavior: str | None,
        status: str,
        result_summary: str | None,
        changed_paths: list[str],
        failure_details: str | None,
        created_at: str,
        updated_at: str,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        with self.database.transaction() as conn:
            conn.execute(
                """
                INSERT INTO tendril_steps (
                    id, plan_id, task_id, step_index, action_type, required_tool, local_action,
                    inputs_json, expected_output, risk_level, approval_required, retry_policy_json,
                    fallback_behavior, status, result_summary, changed_paths_json, failure_details,
                    created_at, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    action_type = excluded.action_type,
                    required_tool = excluded.required_tool,
                    local_action = excluded.local_action,
                    inputs_json = excluded.inputs_json,
                    expected_output = excluded.expected_output,
                    risk_level = excluded.risk_level,
                    approval_required = excluded.approval_required,
                    retry_policy_json = excluded.retry_policy_json,
                    fallback_behavior = excluded.fallback_behavior,
                    status = excluded.status,
                    result_summary = excluded.result_summary,
                    changed_paths_json = excluded.changed_paths_json,
                    failure_details = excluded.failure_details,
                    updated_at = excluded.updated_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    step_id,
                    plan_id,
                    task_id,
                    step_index,
                    action_type,
                    required_tool,
                    local_action,
                    _json_dumps(inputs),
                    expected_output,
                    risk_level,
                    1 if approval_required else 0,
                    _json_dumps(retry_policy),
                    fallback_behavior,
                    status,
                    result_summary,
                    _json_dumps(changed_paths),
                    failure_details,
                    created_at,
                    updated_at,
                    _json_dumps(metadata or {}),
                ),
            )
            row = conn.execute("SELECT * FROM tendril_steps WHERE id = ?", (step_id,)).fetchone()
        return _decode_row(row, json_fields=self.STEP_JSON_FIELDS) or {}

    def list_steps(self, *, task_id: str | None = None, plan_id: str | None = None) -> list[dict[str, object]]:
        clauses: list[str] = []
        params: list[object] = []
        if task_id:
            clauses.append("task_id = ?")
            params.append(task_id)
        if plan_id:
            clauses.append("plan_id = ?")
            params.append(plan_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.database.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM tendril_steps
                {where}
                ORDER BY step_index ASC, id ASC
                """,
                tuple(params),
            ).fetchall()
        return [_decode_row(row, json_fields=self.STEP_JSON_FIELDS) or {} for row in rows]

    def append_audit_event(
        self,
        *,
        event_id: str,
        task_id: str,
        plan_id: str | None,
        step_id: str | None,
        event_type: str,
        rationale: str | None,
        action_taken: str | None,
        tool_used: str | None,
        changed_paths: list[str],
        failure_details: str | None,
        reversal_conditions: list[str],
        created_at: str,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        with self.database.transaction() as conn:
            conn.execute(
                """
                INSERT INTO tendril_audit_events (
                    id, task_id, plan_id, step_id, event_type, rationale, action_taken,
                    tool_used, changed_paths_json, failure_details, reversal_conditions_json,
                    created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    task_id,
                    plan_id,
                    step_id,
                    event_type,
                    rationale,
                    action_taken,
                    tool_used,
                    _json_dumps(changed_paths),
                    failure_details,
                    _json_dumps(reversal_conditions),
                    created_at,
                    _json_dumps(metadata or {}),
                ),
            )
            row = conn.execute("SELECT * FROM tendril_audit_events WHERE id = ?", (event_id,)).fetchone()
        return _decode_row(row, json_fields=self.AUDIT_JSON_FIELDS) or {}

    def list_audit_events(self, task_id: str, *, limit: int = 200) -> list[dict[str, object]]:
        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tendril_audit_events
                WHERE task_id = ?
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """,
                (task_id, max(int(limit), 1)),
            ).fetchall()
        return [_decode_row(row, json_fields=self.AUDIT_JSON_FIELDS) or {} for row in rows]

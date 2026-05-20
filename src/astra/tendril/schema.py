from __future__ import annotations

import sqlite3


class TendrilSchema:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def initialize(self) -> None:
        self.connection.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS tendril_tasks (
                id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
                intent_summary TEXT,
                risk_level TEXT NOT NULL,
                required_tools_json TEXT NOT NULL,
                status TEXT NOT NULL,
                approval_state TEXT NOT NULL,
                project_id TEXT,
                session_id TEXT,
                completion_criteria_json TEXT NOT NULL,
                archive_state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                approved_at TEXT,
                completed_at TEXT,
                metadata_json TEXT
            );

            CREATE TABLE IF NOT EXISTS tendril_plans (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                status TEXT NOT NULL,
                planner_rationale TEXT,
                current_step_index INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata_json TEXT,
                FOREIGN KEY(task_id) REFERENCES tendril_tasks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tendril_steps (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                required_tool TEXT,
                local_action TEXT,
                inputs_json TEXT NOT NULL,
                expected_output TEXT,
                risk_level TEXT NOT NULL,
                approval_required INTEGER NOT NULL,
                retry_policy_json TEXT NOT NULL,
                fallback_behavior TEXT,
                status TEXT NOT NULL,
                result_summary TEXT,
                changed_paths_json TEXT NOT NULL,
                failure_details TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata_json TEXT,
                FOREIGN KEY(plan_id) REFERENCES tendril_plans(id) ON DELETE CASCADE,
                FOREIGN KEY(task_id) REFERENCES tendril_tasks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tendril_audit_events (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                plan_id TEXT,
                step_id TEXT,
                event_type TEXT NOT NULL,
                rationale TEXT,
                action_taken TEXT,
                tool_used TEXT,
                changed_paths_json TEXT NOT NULL,
                failure_details TEXT,
                reversal_conditions_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata_json TEXT,
                FOREIGN KEY(task_id) REFERENCES tendril_tasks(id) ON DELETE CASCADE,
                FOREIGN KEY(plan_id) REFERENCES tendril_plans(id) ON DELETE SET NULL,
                FOREIGN KEY(step_id) REFERENCES tendril_steps(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tendril_tasks_session ON tendril_tasks(session_id, updated_at);
            CREATE INDEX IF NOT EXISTS idx_tendril_tasks_project ON tendril_tasks(project_id, updated_at);
            CREATE INDEX IF NOT EXISTS idx_tendril_tasks_status ON tendril_tasks(status);
            CREATE INDEX IF NOT EXISTS idx_tendril_plans_task ON tendril_plans(task_id, version);
            CREATE INDEX IF NOT EXISTS idx_tendril_steps_task ON tendril_steps(task_id, step_index);
            CREATE INDEX IF NOT EXISTS idx_tendril_steps_plan ON tendril_steps(plan_id, step_index);
            CREATE INDEX IF NOT EXISTS idx_tendril_audit_task ON tendril_audit_events(task_id, created_at);
            """
        )
        self.connection.commit()

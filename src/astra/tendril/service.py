from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

from .persistence import TendrilPersistence
from .settings import TendrilSettings


TASK_STATUSES = {"draft", "awaiting_approval", "running", "paused", "blocked", "completed", "failed", "archived"}
STEP_STATUSES = {"draft", "awaiting_approval", "running", "completed", "failed", "blocked", "skipped"}
APPROVAL_REQUIRED_ACTIONS = {"create_directory", "write_text_file", "save_plan_file"}
REJECTED_ACTIONS = {
    "delete",
    "delete_file",
    "delete_directory",
    "external_post",
    "send_message",
    "financial_action",
    "account_change",
    "network_action",
    "shell",
    "run_shell",
}


@dataclass(slots=True)
class TendrilStepSpec:
    action_type: str
    local_action: str | None
    inputs: dict[str, object]
    expected_output: str
    rationale: str
    risk_level: str = "medium"
    approval_required: bool = True
    required_tool: str | None = None
    retry_policy: dict[str, object] = field(default_factory=lambda: {"max_attempts": 1})
    fallback_behavior: str = "pause_and_report"


class TendrilPlanner:
    """Builds conservative Astra-local Tendril plans from explicit user goals."""

    def build_plan(self, *, goal: str, workspace_name: str | None = None) -> tuple[str, list[str], list[TendrilStepSpec]]:
        normalized_goal = " ".join(str(goal or "").strip().split())
        if not normalized_goal:
            raise ValueError("Tendril goal is required")
        folder_name = self._safe_folder_name(workspace_name or "tendril_project")
        summary_text = (
            "# Astra Tendril Workflow Summary\n\n"
            f"Goal: {normalized_goal}\n\n"
            "Status: prepared by Astra Tendril after explicit approval.\n"
            "Authority: local approved execution only; no external posting, messaging, or irreversible action.\n"
        )
        plan_text = (
            "# Astra Tendril Task Plan\n\n"
            f"Goal: {normalized_goal}\n\n"
            "1. Create the bounded workspace folder.\n"
            "2. Save a workflow summary.\n"
            "3. Save this task plan.\n"
            "4. Report completion with changed paths.\n"
        )
        steps = [
            TendrilStepSpec(
                action_type="local_workspace",
                local_action="create_directory",
                inputs={"path": f"workspaces/{folder_name}"},
                expected_output="Workspace folder exists inside Astra Tendril data.",
                rationale="The requested workflow needs a bounded local folder before writing artifacts.",
            ),
            TendrilStepSpec(
                action_type="local_workspace",
                local_action="write_text_file",
                inputs={"path": f"workspaces/{folder_name}/summary.md", "content": summary_text},
                expected_output="Summary file saved inside the approved workspace folder.",
                rationale="The workflow asks Astra to generate and save a summary file.",
            ),
            TendrilStepSpec(
                action_type="local_workspace",
                local_action="save_plan_file",
                inputs={"path": f"workspaces/{folder_name}/task_plan.md", "content": plan_text},
                expected_output="Task plan file saved inside the approved workspace folder.",
                rationale="The workflow asks Astra to save the executable task plan.",
            ),
            TendrilStepSpec(
                action_type="report",
                local_action="report_completion",
                inputs={"message": "Astra Tendril workflow completed."},
                expected_output="Completion is reported with the changed paths.",
                rationale="Astra should close the workflow by reporting what happened.",
                risk_level="low",
                approval_required=False,
            ),
        ]
        criteria = [
            "workspace folder exists",
            "summary file exists",
            "task plan file exists",
            "audit trail records changed paths",
        ]
        return folder_name, criteria, steps

    @staticmethod
    def _safe_folder_name(value: str) -> str:
        normalized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value).lower())
        normalized = "-".join(part for part in normalized.split("-") if part)
        return normalized[:64] or "tendril_project"


class TendrilPermissionGate:
    """Approval and risk checks for Astra Tendril steps."""

    def evaluate(self, *, step: dict[str, object], task: dict[str, object]) -> dict[str, object]:
        action = str(step.get("local_action") or step.get("action_type") or "").strip()
        if action in REJECTED_ACTIONS:
            return {
                "allowed": False,
                "approval_required": True,
                "reason": f"'{action}' is outside Astra Tendril V1 execution scope.",
                "authority_status": "blocked_by_policy",
            }
        approval_required = bool(step.get("approval_required")) or action in APPROVAL_REQUIRED_ACTIONS
        approved = str(task.get("approval_state") or "") == "approved"
        if approval_required and not approved:
            return {
                "allowed": False,
                "approval_required": True,
                "reason": "Mutating Tendril steps require explicit approval before execution.",
                "authority_status": "awaiting_user_approval",
            }
        return {
            "allowed": True,
            "approval_required": approval_required,
            "reason": "Step is within approved local Astra Tendril scope.",
            "authority_status": "approved_local_execution" if approved else "non_mutating_or_report",
        }


class TendrilAuditTrail:
    def __init__(self, *, settings: TendrilSettings, persistence: TendrilPersistence):
        self.settings = settings
        self.persistence = persistence
        self.root = settings.data_root / "audit"

    def record(
        self,
        *,
        task_id: str,
        event_type: str,
        rationale: str | None = None,
        plan_id: str | None = None,
        step_id: str | None = None,
        action_taken: str | None = None,
        tool_used: str | None = None,
        changed_paths: list[str] | None = None,
        failure_details: str | None = None,
        reversal_conditions: list[str] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        created_at = datetime.now(UTC).isoformat()
        event_id = TendrilService.stable_id("tendril_audit", f"{task_id}|{event_type}|{created_at}|{step_id or ''}")
        row = self.persistence.tendril.append_audit_event(
            event_id=event_id,
            task_id=task_id,
            plan_id=plan_id,
            step_id=step_id,
            event_type=event_type,
            rationale=rationale,
            action_taken=action_taken,
            tool_used=tool_used,
            changed_paths=list(changed_paths or []),
            failure_details=failure_details,
            reversal_conditions=list(reversal_conditions or []),
            created_at=created_at,
            metadata=metadata or {},
        )
        self._write_fallback(task_id=task_id, event=row)
        return row

    def _write_fallback(self, *, task_id: str, event: dict[str, object]) -> None:
        target = self.root / task_id
        target.mkdir(parents=True, exist_ok=True)
        event_id = str(event.get("id") or "event")
        (target / f"{event_id}.json").write_text(json.dumps(event, indent=2), encoding="utf-8")


class TendrilService:
    """Astra-local Tendril orchestration."""

    def __init__(
        self,
        *,
        settings: TendrilSettings | None = None,
        persistence: TendrilPersistence | None = None,
    ) -> None:
        self.settings = settings or TendrilSettings.from_repo_root()
        self.persistence = persistence or TendrilPersistence(self.settings)
        self.planner = TendrilPlanner()
        self.permission_gate = TendrilPermissionGate()
        self.audit_trail = TendrilAuditTrail(settings=self.settings, persistence=self.persistence)

    def create_task(
        self,
        *,
        goal: str,
        session_id: str = "default",
        project_id: str | None = None,
        workspace_name: str | None = None,
    ) -> dict[str, object]:
        self.persistence.bootstrap()
        now = datetime.now(UTC).isoformat()
        folder_name, completion_criteria, step_specs = self.planner.build_plan(goal=goal, workspace_name=workspace_name)
        task_id = self.stable_id("tendril_task", f"{session_id}|{goal}|{now}")
        plan_id = self.stable_id("tendril_plan", f"{task_id}|1")
        risk_level = "medium" if any(step.approval_required for step in step_specs) else "low"
        status = "awaiting_approval" if any(step.approval_required for step in step_specs) else "draft"
        task = self.persistence.tendril.upsert_task(
            task_id=task_id,
            goal=goal,
            intent_summary=f"Approved local Astra Tendril workflow for {folder_name}.",
            risk_level=risk_level,
            required_tools=[],
            status=status,
            approval_state="not_requested",
            project_id=project_id,
            session_id=session_id,
            completion_criteria=completion_criteria,
            archive_state="active",
            created_at=now,
            updated_at=now,
            metadata={"advisory_only": True, "workspace_name": folder_name},
        )
        plan = self.persistence.tendril.upsert_plan(
            plan_id=plan_id,
            task_id=task_id,
            version=1,
            status="draft",
            planner_rationale="Astra Tendril created a conservative approved-local workflow plan.",
            current_step_index=0,
            created_at=now,
            updated_at=now,
            metadata={"approval_required": True, "advisory_until_approved": True},
        )
        steps = []
        for index, spec in enumerate(step_specs):
            step_id = self.stable_id("tendril_step", f"{plan_id}|{index}|{spec.local_action}")
            steps.append(
                self.persistence.tendril.upsert_step(
                    step_id=step_id,
                    plan_id=plan_id,
                    task_id=task_id,
                    step_index=index,
                    action_type=spec.action_type,
                    required_tool=spec.required_tool,
                    local_action=spec.local_action,
                    inputs=spec.inputs,
                    expected_output=spec.expected_output,
                    risk_level=spec.risk_level,
                    approval_required=spec.approval_required,
                    retry_policy=spec.retry_policy,
                    fallback_behavior=spec.fallback_behavior,
                    status="awaiting_approval" if spec.approval_required else "draft",
                    result_summary=None,
                    changed_paths=[],
                    failure_details=None,
                    created_at=now,
                    updated_at=now,
                    metadata={"rationale": spec.rationale},
                )
            )
        self.audit_trail.record(
            task_id=task_id,
            plan_id=plan_id,
            event_type="plan_created",
            rationale="Tendril can plan freely, but execution remains blocked until approval.",
            action_taken="created draft plan",
            reversal_conditions=["archive task if the goal is no longer wanted"],
        )
        return self._task_payload(task=task, plan=plan, steps=steps)

    def approve_task(self, task_id: str) -> dict[str, object]:
        task = self._require_task(task_id)
        now = datetime.now(UTC).isoformat()
        task = self.persistence.tendril.upsert_task(
            task_id=str(task["id"]),
            goal=str(task["goal"]),
            intent_summary=str(task.get("intent_summary") or "") or None,
            risk_level=str(task["risk_level"]),
            required_tools=list(task.get("required_tools_json") or []),
            status="awaiting_approval" if str(task.get("status")) == "draft" else str(task.get("status")),
            approval_state="approved",
            project_id=str(task.get("project_id") or "") or None,
            session_id=str(task.get("session_id") or "") or None,
            completion_criteria=list(task.get("completion_criteria_json") or []),
            archive_state=str(task.get("archive_state") or "active"),
            created_at=str(task["created_at"]),
            updated_at=now,
            approved_at=now,
            completed_at=str(task.get("completed_at") or "") or None,
            metadata=dict(task.get("metadata_json") or {}),
        )
        plan = self.persistence.tendril.latest_plan_for_task(task_id)
        self.audit_trail.record(
            task_id=task_id,
            plan_id=str((plan or {}).get("id") or "") or None,
            event_type="approved",
            rationale="User explicitly approved local Astra Tendril execution.",
            action_taken="approved task",
            reversal_conditions=["archive task", "manually delete generated files if no longer wanted"],
        )
        return self.show_task(task_id)

    def run_task(self, task_id: str) -> dict[str, object]:
        task = self._require_task(task_id)
        plan = self._require_plan(task_id)
        steps = self.persistence.tendril.list_steps(task_id=task_id, plan_id=str(plan["id"]))
        if str(task.get("approval_state") or "") != "approved":
            self.audit_trail.record(
                task_id=task_id,
                plan_id=str(plan["id"]),
                event_type="blocked",
                rationale="Tendril refused to run because approval is missing.",
                action_taken="blocked run",
                failure_details="Task approval_state is not approved.",
            )
            payload = self.show_task(task_id)
            payload.update({"status": "blocked", "schema_type": "tendril_run_result", "reason": "approval_required"})
            return payload
        now = datetime.now(UTC).isoformat()
        task = self._update_task_status(task, status="running", updated_at=now)
        changed_paths: list[str] = []
        completed_steps = 0
        failed_step: dict[str, object] | None = None
        for step in steps:
            if str(step.get("status")) == "completed":
                completed_steps += 1
                changed_paths.extend(str(path) for path in (step.get("changed_paths_json") or []))
                continue
            gate = self.permission_gate.evaluate(step=step, task=task)
            if not gate["allowed"]:
                failed_step = self._mark_step_failed(step, reason=str(gate["reason"]), blocked=True)
                break
            running_step = self._update_step_status(step, status="running")
            try:
                result = self._execute_local_step(running_step)
            except Exception as exc:
                failed_step = self._mark_step_failed(running_step, reason=str(exc), blocked=False)
                break
            changed_paths.extend(result["changed_paths"])
            self.persistence.tendril.upsert_step(
                **self._step_upsert_args(running_step),
                status="completed",
                result_summary=result["summary"],
                changed_paths=result["changed_paths"],
                failure_details=None,
                updated_at=datetime.now(UTC).isoformat(),
            )
            self.audit_trail.record(
                task_id=task_id,
                plan_id=str(plan["id"]),
                step_id=str(step["id"]),
                event_type="step_completed",
                rationale=str((step.get("metadata_json") or {}).get("rationale") or "Approved Tendril step completed."),
                action_taken=str(step.get("local_action") or step.get("action_type")),
                changed_paths=result["changed_paths"],
                reversal_conditions=result["reversal_conditions"],
            )
            completed_steps += 1
        if failed_step is not None:
            task = self._update_task_status(task, status="blocked" if failed_step.get("status") == "blocked" else "failed")
            self.audit_trail.record(
                task_id=task_id,
                plan_id=str(plan["id"]),
                step_id=str(failed_step.get("id") or ""),
                event_type=str(task["status"]),
                rationale="Tendril stopped instead of pushing past a failed step.",
                action_taken="paused execution",
                failure_details=str(failed_step.get("failure_details") or ""),
                reversal_conditions=["fix the blocked condition and rerun", "archive task"],
            )
            return {
                "status": str(task["status"]),
                "schema_type": "tendril_run_result",
                "task": task,
                "completed_steps": completed_steps,
                "changed_paths": changed_paths,
                "failed_step": failed_step,
            }
        task = self._update_task_status(task, status="completed", completed_at=datetime.now(UTC).isoformat())
        self.audit_trail.record(
            task_id=task_id,
            plan_id=str(plan["id"]),
            event_type="completed",
            rationale="All approved Astra Tendril steps completed in order.",
            action_taken="completed workflow",
            changed_paths=changed_paths,
            reversal_conditions=["archive task", "manually remove generated files if desired"],
        )
        return {
            "status": "completed",
            "schema_type": "tendril_run_result",
            "task": task,
            "completed_steps": completed_steps,
            "changed_paths": changed_paths,
        }

    def show_task(self, task_id: str) -> dict[str, object]:
        task = self._require_task(task_id)
        plan = self.persistence.tendril.latest_plan_for_task(task_id)
        steps = self.persistence.tendril.list_steps(task_id=task_id, plan_id=str((plan or {}).get("id") or "") or None)
        return self._task_payload(task=task, plan=plan, steps=steps)

    def list_tasks(
        self,
        *,
        session_id: str | None = None,
        project_id: str | None = None,
        status: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> dict[str, object]:
        self.persistence.bootstrap()
        tasks = self.persistence.tendril.list_tasks(
            session_id=session_id,
            project_id=project_id,
            status=status,
            include_archived=include_archived,
            limit=limit,
        )
        return {
            "status": "ok",
            "schema_type": "tendril_task_list",
            "task_count": len(tasks),
            "tasks": tasks,
        }

    def archive_task(self, task_id: str) -> dict[str, object]:
        task = self._require_task(task_id)
        task = self.persistence.tendril.upsert_task(
            task_id=str(task["id"]),
            goal=str(task["goal"]),
            intent_summary=str(task.get("intent_summary") or "") or None,
            risk_level=str(task["risk_level"]),
            required_tools=list(task.get("required_tools_json") or []),
            status="archived",
            approval_state=str(task.get("approval_state") or "not_requested"),
            project_id=str(task.get("project_id") or "") or None,
            session_id=str(task.get("session_id") or "") or None,
            completion_criteria=list(task.get("completion_criteria_json") or []),
            archive_state="archived",
            created_at=str(task["created_at"]),
            updated_at=datetime.now(UTC).isoformat(),
            approved_at=str(task.get("approved_at") or "") or None,
            completed_at=str(task.get("completed_at") or "") or None,
            metadata=dict(task.get("metadata_json") or {}),
        )
        self.audit_trail.record(
            task_id=task_id,
            event_type="archived",
            rationale="User archived the Tendril task.",
            action_taken="archived task",
        )
        return {"status": "ok", "schema_type": "tendril_archive_result", "task": task}

    def audit_report(self, task_id: str) -> dict[str, object]:
        task = self._require_task(task_id)
        events = self.persistence.tendril.list_audit_events(task_id, limit=500)
        return {
            "status": "ok",
            "schema_type": "tendril_audit_report",
            "task": task,
            "event_count": len(events),
            "events": events,
        }

    def _execute_local_step(self, step: dict[str, object]) -> dict[str, object]:
        action = str(step.get("local_action") or "").strip()
        inputs = dict(step.get("inputs_json") or {})
        if action == "create_directory":
            target = self._resolve_allowed_path(inputs.get("path"))
            target.mkdir(parents=True, exist_ok=True)
            return {
                "summary": f"Created directory {target}",
                "changed_paths": [str(target)],
                "reversal_conditions": ["remove directory manually if it is no longer needed"],
            }
        if action in {"write_text_file", "save_plan_file"}:
            target = self._resolve_allowed_path(inputs.get("path"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(inputs.get("content") or ""), encoding="utf-8")
            return {
                "summary": f"Wrote file {target}",
                "changed_paths": [str(target)],
                "reversal_conditions": ["edit or remove generated file manually if it is no longer wanted"],
            }
        if action == "report_completion":
            return {"summary": str(inputs.get("message") or "Astra Tendril workflow completed."), "changed_paths": [], "reversal_conditions": []}
        raise ValueError(f"Unsupported Astra Tendril V1 local action: {action}")

    def _resolve_allowed_path(self, value: object) -> Path:
        raw = str(value or "").strip()
        if not raw:
            raise ValueError("Tendril local action requires a path")
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = self.settings.data_root / candidate
        resolved = candidate.resolve()
        allowed_roots = [
            self.settings.repo_root.resolve(),
            self.settings.data_root.resolve(),
        ]
        if not any(self._is_relative_to(resolved, root) for root in allowed_roots):
            raise ValueError(f"Tendril path must stay inside the repo or data root: {resolved}")
        return resolved

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _update_task_status(
        self,
        task: dict[str, object],
        *,
        status: str,
        updated_at: str | None = None,
        completed_at: str | None = None,
    ) -> dict[str, object]:
        if status not in TASK_STATUSES:
            raise ValueError(f"Unsupported Tendril task status: {status}")
        return self.persistence.tendril.upsert_task(
            task_id=str(task["id"]),
            goal=str(task["goal"]),
            intent_summary=str(task.get("intent_summary") or "") or None,
            risk_level=str(task["risk_level"]),
            required_tools=list(task.get("required_tools_json") or []),
            status=status,
            approval_state=str(task.get("approval_state") or "not_requested"),
            project_id=str(task.get("project_id") or "") or None,
            session_id=str(task.get("session_id") or "") or None,
            completion_criteria=list(task.get("completion_criteria_json") or []),
            archive_state=str(task.get("archive_state") or "active"),
            created_at=str(task["created_at"]),
            updated_at=updated_at or datetime.now(UTC).isoformat(),
            approved_at=str(task.get("approved_at") or "") or None,
            completed_at=completed_at or str(task.get("completed_at") or "") or None,
            metadata=dict(task.get("metadata_json") or {}),
        )

    def _update_step_status(self, step: dict[str, object], *, status: str) -> dict[str, object]:
        return self.persistence.tendril.upsert_step(
            **self._step_upsert_args(step),
            status=status,
            result_summary=str(step.get("result_summary") or "") or None,
            changed_paths=list(step.get("changed_paths_json") or []),
            failure_details=str(step.get("failure_details") or "") or None,
            updated_at=datetime.now(UTC).isoformat(),
        )

    def _mark_step_failed(self, step: dict[str, object], *, reason: str, blocked: bool) -> dict[str, object]:
        return self.persistence.tendril.upsert_step(
            **self._step_upsert_args(step),
            status="blocked" if blocked else "failed",
            result_summary=None,
            changed_paths=list(step.get("changed_paths_json") or []),
            failure_details=reason,
            updated_at=datetime.now(UTC).isoformat(),
        )

    @staticmethod
    def _step_upsert_args(step: dict[str, object]) -> dict[str, object]:
        return {
            "step_id": str(step["id"]),
            "plan_id": str(step["plan_id"]),
            "task_id": str(step["task_id"]),
            "step_index": int(step["step_index"]),
            "action_type": str(step["action_type"]),
            "required_tool": str(step.get("required_tool") or "") or None,
            "local_action": str(step.get("local_action") or "") or None,
            "inputs": dict(step.get("inputs_json") or {}),
            "expected_output": str(step.get("expected_output") or "") or None,
            "risk_level": str(step["risk_level"]),
            "approval_required": bool(step.get("approval_required")),
            "retry_policy": dict(step.get("retry_policy_json") or {}),
            "fallback_behavior": str(step.get("fallback_behavior") or "") or None,
            "created_at": str(step["created_at"]),
            "metadata": dict(step.get("metadata_json") or {}),
        }

    def _require_task(self, task_id: str) -> dict[str, object]:
        self.persistence.bootstrap()
        task = self.persistence.tendril.get_task(task_id)
        if task is None:
            raise ValueError(f"Unknown Tendril task: {task_id}")
        return task

    def _require_plan(self, task_id: str) -> dict[str, object]:
        plan = self.persistence.tendril.latest_plan_for_task(task_id)
        if plan is None:
            raise ValueError(f"Tendril task has no plan: {task_id}")
        return plan

    @staticmethod
    def _task_payload(
        *,
        task: dict[str, object],
        plan: dict[str, object] | None,
        steps: list[dict[str, object]],
    ) -> dict[str, object]:
        return {
            "status": "ok",
            "schema_type": "tendril_task",
            "task": task,
            "plan": plan,
            "steps": steps,
            "step_count": len(steps),
            "approval_required": any(bool(step.get("approval_required")) for step in steps),
            "advisory_until_approved": str(task.get("approval_state") or "") != "approved",
        }

    @staticmethod
    def stable_id(prefix: str, seed: str) -> str:
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        return f"{prefix}_{digest}"

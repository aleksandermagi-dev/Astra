from __future__ import annotations

from pathlib import Path

import pytest

from astra.tendril.persistence import TendrilPersistence
from astra.tendril.service import REJECTED_ACTIONS, TendrilPermissionGate, TendrilService
from astra.tendril.settings import TendrilSettings


def _service(tmp_path: Path) -> tuple[TendrilService, TendrilPersistence, TendrilSettings]:
    settings = TendrilSettings.from_repo_root(tmp_path, data_root=tmp_path / "outputs" / "tendril")
    persistence = TendrilPersistence(settings)
    persistence.bootstrap()
    return TendrilService(settings=settings, persistence=persistence), persistence, settings


def test_tendril_create_persists_task_plan_steps_and_audit(tmp_path: Path) -> None:
    service, persistence, _ = _service(tmp_path)

    report = service.create_task(
        goal="Create a campaign folder, generate a summary file, save a task plan, and report completion.",
        session_id="tendril-session",
        project_id="astra",
        workspace_name="first workflow",
    )

    task = report["task"]
    steps = report["steps"]
    audit = persistence.tendril.list_audit_events(str(task["id"]))

    assert report["schema_type"] == "tendril_task"
    assert task["status"] == "awaiting_approval"
    assert task["approval_state"] == "not_requested"
    assert report["approval_required"] is True
    assert [step["local_action"] for step in steps] == [
        "create_directory",
        "write_text_file",
        "save_plan_file",
        "report_completion",
    ]
    assert audit[0]["event_type"] == "plan_created"


def test_permission_gate_blocks_mutating_step_before_approval(tmp_path: Path) -> None:
    service, _, _ = _service(tmp_path)
    report = service.create_task(goal="Create a folder", session_id="gate-session")
    task = report["task"]
    step = report["steps"][0]

    decision = TendrilPermissionGate().evaluate(step=step, task=task)

    assert decision["allowed"] is False
    assert decision["authority_status"] == "awaiting_user_approval"


def test_permission_gate_blocks_rejected_actions() -> None:
    for action in REJECTED_ACTIONS:
        decision = TendrilPermissionGate().evaluate(
            step={"local_action": action, "approval_required": False},
            task={"approval_state": "approved"},
        )
        assert decision["allowed"] is False
        assert decision["authority_status"] == "blocked_by_policy"


def test_tendril_approved_workflow_executes_and_records_paths(tmp_path: Path) -> None:
    service, _, settings = _service(tmp_path)
    created = service.create_task(
        goal="Create a campaign folder, generate a summary file, save a task plan, and report completion.",
        session_id="run-session",
        project_id="astra",
        workspace_name="acceptance workflow",
    )
    task_id = str(created["task"]["id"])

    approved = service.approve_task(task_id)
    run = service.run_task(task_id)
    shown = service.show_task(task_id)

    assert approved["task"]["approval_state"] == "approved"
    assert run["status"] == "completed"
    assert shown["task"]["status"] == "completed"
    assert all(step["status"] == "completed" for step in shown["steps"])
    assert (settings.data_root / "workspaces" / "acceptance-workflow" / "summary.md").exists()
    assert (settings.data_root / "workspaces" / "acceptance-workflow" / "task_plan.md").exists()
    assert str(settings.data_root / "workspaces" / "acceptance-workflow") in run["changed_paths"]


def test_tendril_rejects_paths_outside_allowed_roots(tmp_path: Path) -> None:
    service, persistence, _ = _service(tmp_path)
    report = service.create_task(goal="Create a folder", session_id="path-session")
    task_id = str(report["task"]["id"])
    step = dict(report["steps"][1])
    inputs = dict(step["inputs_json"])
    inputs["path"] = str(tmp_path.parent / "outside.txt")
    args = service._step_upsert_args(step)
    args["inputs"] = inputs
    persistence.tendril.upsert_step(
        **args,
        status="awaiting_approval",
        result_summary=None,
        changed_paths=[],
        failure_details=None,
        updated_at=step["updated_at"],
    )

    service.approve_task(task_id)
    run = service.run_task(task_id)

    assert run["status"] == "failed"
    assert "Tendril path must stay inside" in run["failed_step"]["failure_details"]


def test_tendril_archive_and_audit_report(tmp_path: Path) -> None:
    service, _, _ = _service(tmp_path)
    report = service.create_task(goal="Create a folder", session_id="archive-session")
    task_id = str(report["task"]["id"])

    archived = service.archive_task(task_id)
    audit = service.audit_report(task_id)
    listed = service.list_tasks(include_archived=True)

    assert archived["task"]["status"] == "archived"
    assert audit["event_count"] >= 2
    assert any(task["id"] == task_id for task in listed["tasks"])


def test_tendril_unknown_task_errors(tmp_path: Path) -> None:
    service, _, _ = _service(tmp_path)

    with pytest.raises(ValueError, match="Unknown Tendril task"):
        service.show_task("missing-task")

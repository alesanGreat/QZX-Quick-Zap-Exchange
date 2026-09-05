"""Behavioral tests for deterministic workspace audit and repair."""

from __future__ import annotations

import json
import os
import subprocess
import zipfile

from qzx.commands.file.audit_workspace import AuditWorkspaceCommand
from qzx.commands.file.repair_workspace import RepairWorkspaceCommand
import qzx.core.workspace_audit as workspace_audit
from qzx.core.workspace_audit import (
    MAX_PLAN_BYTES,
    WorkspaceAuditError,
    build_workspace_plan,
    plan_id,
)


def _write_plan(path, plan):
    path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _action(plan, *, path=None, kind=None, executable=None):
    return next(
        item
        for item in plan["actions"]
        if (path is None or item["path"] == path)
        and (kind is None or item["kind"] == kind)
        and (executable is None or item["executable"] is executable)
    )


def _create_representative_workspace(root):
    (root / "package.json").write_text("{}", encoding="utf-8")
    (root / "dist").mkdir()
    (root / "dist" / "app.js").write_text("built", encoding="utf-8")
    (root / "debug.tmp").write_text("temporary", encoding="utf-8")
    (root / "valuable.log").write_text("diagnostic", encoding="utf-8")
    (root / "installer.exe").write_bytes(b"deliverable")
    (root / "My Notes.TXT").write_text("keep", encoding="utf-8")
    (root / "original.txt").write_text("identical", encoding="utf-8")
    (root / "duplicate.txt").write_text("identical", encoding="utf-8")


def test_audit_is_deterministic_and_never_mutates_workspace(tmp_path):
    _create_representative_workspace(tmp_path)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    first = build_workspace_plan(tmp_path)
    second = build_workspace_plan(tmp_path)

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert first == second
    assert first["plan_id"].startswith("plan-")
    assert first["scan_complete"] is True
    assert before == after
    assert _action(first, path="dist")["kind"] == "delete_directory"
    assert _action(first, path="debug.tmp")["executable"] is True
    assert _action(first, path="valuable.log")["executable"] is False
    assert _action(first, path="installer.exe")["executable"] is False
    assert _action(first, path="My Notes.TXT")["kind"] == "review_rename"
    assert _action(first, kind="delete_duplicate")["reason"] == (
        "SHA-256 and exact byte match."
    )


def test_audit_can_save_new_plan_but_never_overwrites(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "debug.tmp").write_text("temporary", encoding="utf-8")
    plan_path = tmp_path / "repair-plan.json"
    command = AuditWorkspaceCommand()

    first = command.execute(workspace, plan_file=plan_path)
    second = command.execute(workspace, plan_file=plan_path)

    assert first["success"] is True
    assert first["details"]["workspace_unchanged"] is True
    assert json.loads(plan_path.read_text(encoding="utf-8"))["plan_id"] == (
        first["details"]["plan"]["plan_id"]
    )
    assert second["success"] is False
    assert second["error_code"] == "plan_file_exists"


def test_audit_refuses_to_save_plan_larger_than_repair_can_read(tmp_path):
    plan_path = tmp_path / "oversized.json"
    plan = {
        "root": str(tmp_path),
        "actions": [],
        "padding": "x" * MAX_PLAN_BYTES,
    }

    try:
        AuditWorkspaceCommand._save_new_plan(plan, plan_path)
    except WorkspaceAuditError as exc:
        error = exc
    else:
        raise AssertionError("oversized audit plan was unexpectedly saved")

    assert error.code == "plan_file_too_large"
    assert error.details["plan_size_bytes"] > MAX_PLAN_BYTES
    assert error.details["max_plan_bytes"] == MAX_PLAN_BYTES
    assert not plan_path.exists()


def test_incomplete_scan_is_diagnostic_and_cannot_be_repaired(tmp_path):
    for index in range(3):
        (tmp_path / "file-{}.tmp".format(index)).write_text(
            "temporary",
            encoding="utf-8",
        )
    plan = build_workspace_plan(tmp_path, max_files=2)
    plan_path = _write_plan(tmp_path.parent / "incomplete.json", plan)

    result = RepairWorkspaceCommand().execute(
        tmp_path,
        plan_file=plan_path,
    )

    assert plan["scan_complete"] is False
    assert result["success"] is False
    assert result["error_code"] == "incomplete_plan_refused"
    assert all((tmp_path / "file-{}.tmp".format(index)).exists() for index in range(3))


def test_digest_collision_does_not_create_duplicate_action(tmp_path):
    (tmp_path / "first.bin").write_bytes(b"A" * 1024)
    (tmp_path / "second.bin").write_bytes(b"B" * 1024)

    plan = build_workspace_plan(
        tmp_path,
        categories="duplicates",
        file_hasher=lambda _path: "collision",
    )

    assert not any(
        action["kind"] == "delete_duplicate" for action in plan["actions"]
    )


def test_repair_requires_saved_plan_and_strict_boolean(tmp_path):
    command = RepairWorkspaceCommand()

    missing = command.execute(tmp_path)
    invalid_bool = command.execute(
        tmp_path,
        plan_file=tmp_path / "unused.json",
        dry_run="perhaps",
    )

    assert missing["success"] is False
    assert missing["error_code"] == "plan_file_required"
    assert invalid_bool["success"] is False
    assert invalid_bool["error_code"] == "invalid_boolean"


def test_repair_declares_its_dynamic_result_contract():
    properties = RepairWorkspaceCommand.result_schema["properties"]

    assert properties["status"]["enum"] == [
        "preview",
        "applied",
        "rolled_back",
        "recovery_required",
        "cleanup_incomplete",
    ]
    assert properties["details"]["type"] == "object"


def test_repair_preview_validates_plan_without_mutation(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    candidate = workspace / "debug.tmp"
    candidate.write_text("temporary", encoding="utf-8")
    plan = build_workspace_plan(workspace, categories="temp")
    plan_path = _write_plan(tmp_path / "plan.json", plan)
    action = _action(plan, path="debug.tmp")

    result = RepairWorkspaceCommand().execute(
        workspace,
        plan_file=plan_path,
        action_ids=action["id"],
    )

    assert result["success"] is True
    assert result["status"] == "preview"
    assert result["details"]["workspace_unchanged"] is True
    assert result["details"]["selected_actions"] == [action]
    assert candidate.exists()


def test_public_apply_backs_up_then_applies_only_selected_action(
    monkeypatch,
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    selected_file = workspace / "selected.tmp"
    selected_file.write_text("selected", encoding="utf-8")
    unselected_file = workspace / "unselected.tmp"
    unselected_file.write_text("unselected", encoding="utf-8")
    valuable_log = workspace / "valuable.log"
    valuable_log.write_text("keep", encoding="utf-8")
    plan = build_workspace_plan(workspace, categories="temp")
    plan_path = _write_plan(tmp_path / "plan.json", plan)
    selected = _action(plan, path="selected.tmp")
    backup_directory = tmp_path / "backups"
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(backup_directory))

    result = RepairWorkspaceCommand().invoke(
        [
            str(workspace),
            "--plan-file",
            str(plan_path),
            "--action-ids",
            selected["id"],
            "--dry-run",
            "false",
            "--apply",
        ]
    )

    assert result["success"] is True
    assert not selected_file.exists()
    assert unselected_file.exists()
    assert valuable_log.exists()
    assert not list(workspace.glob(".qzx-repair-stage-*"))
    backup = result["meta"]["safety_backup"]
    assert backup["status"] == "created"
    with zipfile.ZipFile(backup["path"]) as archive:
        selected_members = [
            name for name in archive.namelist() if name.endswith("/selected.tmp")
        ]
        assert len(selected_members) == 1
        assert archive.read(selected_members[0]) == b"selected"


def test_stale_selected_action_fails_before_public_backup(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    candidate = workspace / "debug.tmp"
    candidate.write_text("before", encoding="utf-8")
    plan = build_workspace_plan(workspace, categories="temp")
    plan_path = _write_plan(tmp_path / "plan.json", plan)
    action = _action(plan, path="debug.tmp")
    candidate.write_text("after", encoding="utf-8")
    backup_directory = tmp_path / "backups"
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(backup_directory))

    result = RepairWorkspaceCommand().invoke(
        [
            str(workspace),
            "--plan-file",
            str(plan_path),
            "--action-ids",
            action["id"],
            "--dry-run",
            "false",
            "--apply",
        ]
    )

    assert result["success"] is False
    assert result["error_code"] == "workspace_changed_since_audit"
    assert "safety_backup" not in result["meta"]
    assert candidate.read_text(encoding="utf-8") == "after"
    assert not backup_directory.exists()


def test_tampered_plan_is_rejected(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    candidate = workspace / "debug.tmp"
    candidate.write_text("temporary", encoding="utf-8")
    plan = build_workspace_plan(workspace, categories="temp")
    plan["actions"][0]["reason"] = "tampered"
    plan_path = _write_plan(tmp_path / "tampered.json", plan)

    result = RepairWorkspaceCommand().execute(workspace, plan_file=plan_path)

    assert result["success"] is False
    assert result["error_code"] == "plan_integrity_failed"
    assert candidate.exists()


def test_review_only_action_cannot_be_selected(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact = workspace / "installer.exe"
    artifact.write_bytes(b"keep")
    plan = build_workspace_plan(workspace, categories="artifacts")
    plan_path = _write_plan(tmp_path / "plan.json", plan)
    review = _action(plan, path="installer.exe")

    result = RepairWorkspaceCommand().execute(
        workspace,
        plan_file=plan_path,
        action_ids=review["id"],
        dry_run=False,
        apply=True,
    )

    assert result["success"] is False
    assert result["error_code"] == "review_action_refused"
    assert artifact.exists()


def test_plan_root_must_match_requested_workspace(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "debug.tmp").write_text("temporary", encoding="utf-8")
    plan = build_workspace_plan(first, categories="temp")
    plan_path = _write_plan(tmp_path / "plan.json", plan)

    result = RepairWorkspaceCommand().execute(second, plan_file=plan_path)

    assert result["success"] is False
    assert result["error_code"] == "plan_root_mismatch"
    assert (first / "debug.tmp").exists()


def test_duplicate_source_change_invalidates_duplicate_action(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "first.txt").write_text("same", encoding="utf-8")
    (workspace / "second.txt").write_text("same", encoding="utf-8")
    plan = build_workspace_plan(workspace, categories="duplicates")
    plan_path = _write_plan(tmp_path / "plan.json", plan)
    duplicate = _action(plan, kind="delete_duplicate")
    (workspace / duplicate["duplicate_of"]).write_text("changed", encoding="utf-8")

    result = RepairWorkspaceCommand().execute(
        workspace,
        plan_file=plan_path,
        action_ids=duplicate["id"],
    )

    assert result["success"] is False
    assert result["error_code"] == "workspace_changed_since_audit"
    assert (workspace / duplicate["path"]).exists()


def test_staging_failure_rolls_back_every_staged_entry(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    first = workspace / "first.tmp"
    second = workspace / "second.tmp"
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    plan = build_workspace_plan(workspace, categories="temp")
    plan_path = _write_plan(tmp_path / "plan.json", plan)
    actions = [
        _action(plan, path="first.tmp"),
        _action(plan, path="second.tmp"),
    ]
    real_rename = os.rename
    staging_calls = 0

    def fail_second_staging(source, destination):
        nonlocal staging_calls
        if ".qzx-repair-stage-" in os.fspath(destination):
            staging_calls += 1
            if staging_calls == 2:
                raise OSError("simulated staging failure")
        return real_rename(source, destination)

    result = RepairWorkspaceCommand(
        rename_operation=fail_second_staging,
    ).execute(
        workspace,
        plan_file=plan_path,
        action_ids=",".join(action["id"] for action in actions),
        dry_run=False,
        apply=True,
    )

    assert result["success"] is False
    assert result["status"] == "rolled_back"
    assert result["details"]["workspace_restored"] is True
    assert first.read_text(encoding="utf-8") == "one"
    assert second.read_text(encoding="utf-8") == "two"
    assert not list(workspace.glob(".qzx-repair-stage-*"))


def test_plan_file_cannot_be_saved_inside_proposed_directory_deletion(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "package.json").write_text("{}", encoding="utf-8")
    (workspace / "dist").mkdir()
    (workspace / "dist" / "built.js").write_text("built", encoding="utf-8")

    result = AuditWorkspaceCommand().execute(
        workspace,
        categories="build",
        plan_file=workspace / "dist" / "repair-plan.json",
    )

    assert result["success"] is False
    assert result["error_code"] == "plan_file_inside_cleanup_target"
    assert not (workspace / "dist" / "repair-plan.json").exists()


def test_recomputed_plan_id_does_not_make_tampered_action_id_valid(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "debug.tmp").write_text("temporary", encoding="utf-8")
    plan = build_workspace_plan(workspace, categories="temp")
    plan["actions"][0]["id"] = "act-forged"
    plan["plan_id"] = plan_id(plan)
    plan_path = _write_plan(tmp_path / "forged.json", plan)

    result = RepairWorkspaceCommand().execute(workspace, plan_file=plan_path)

    assert result["success"] is False
    assert result["error_code"] == "plan_integrity_failed"


def test_windows_junction_fallback_without_native_isjunction(tmp_path, monkeypatch):
    if os.name != "nt":
        return

    target = tmp_path / "target"
    junction = tmp_path / "junction"
    target.mkdir()
    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(target)],
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout

    monkeypatch.delattr(os.path, "isjunction", raising=False)
    assert workspace_audit._is_junction(junction) is True
    junction.rmdir()


def test_action_ancestor_replaced_by_link_is_refused(tmp_path):
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    parent = workspace / "nested"
    parent.mkdir()
    (parent / "debug.tmp").write_text("inside", encoding="utf-8")
    (outside / "debug.tmp").write_text("outside", encoding="utf-8")
    plan = build_workspace_plan(workspace, categories="temp")
    plan_path = _write_plan(tmp_path / "plan.json", plan)
    action = _action(plan, path="nested/debug.tmp")
    (parent / "debug.tmp").unlink()
    parent.rmdir()
    if os.name == "nt":
        completed = subprocess.run(
            [
                "cmd.exe",
                "/d",
                "/c",
                "mklink",
                "/J",
                str(parent),
                str(outside),
            ],
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr or completed.stdout
    else:
        parent.symlink_to(outside, target_is_directory=True)

    result = RepairWorkspaceCommand().execute(
        workspace,
        plan_file=plan_path,
        action_ids=action["id"],
    )

    assert result["success"] is False
    assert result["error_code"] == "action_ancestor_link_refused"
    assert (outside / "debug.tmp").read_text(encoding="utf-8") == "outside"

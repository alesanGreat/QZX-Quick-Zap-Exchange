"""Focused public-contract tests for auditWorkspace."""

from qzx.commands.file.audit_workspace import AuditWorkspaceCommand


def test_audit_command_reports_incomplete_scan_without_mutation(tmp_path):
    for index in range(3):
        (tmp_path / "file-{}.tmp".format(index)).write_text(
            "temporary",
            encoding="utf-8",
        )

    result = AuditWorkspaceCommand().execute(tmp_path, max_files=2)

    assert result["success"] is False
    assert result["status"] == "incomplete"
    assert result["details"]["workspace_unchanged"] is True
    assert result["details"]["plan"]["scan_complete"] is False
    assert all(
        (tmp_path / "file-{}.tmp".format(index)).exists()
        for index in range(3)
    )

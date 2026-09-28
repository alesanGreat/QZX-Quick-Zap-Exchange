#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the AuditRepository command
"""

import subprocess
import threading
import urllib.error

from qzx.commands.development.audit_repository import AuditRepositoryCommand


class RefusingNetworkAuditRepositoryCommand(AuditRepositoryCommand):
    """Record external checks without contacting a network."""

    def __init__(self):
        super().__init__()
        self.requested_urls = []

    def _open_url(self, request, timeout):
        self.requested_urls.append(request.full_url)
        raise urllib.error.URLError("synthetic unavailable host")

class FailingHashAuditRepositoryCommand(AuditRepositoryCommand):
    """Deterministic fake for an unreadable audited file."""

    @staticmethod
    def _hash_file(_path):
        raise OSError("synthetic read failure")


class TinyLimitAuditRepositoryCommand(AuditRepositoryCommand):
    """Use a tiny scan budget to exercise bounded-audit behavior."""

    max_audit_files = 2


class TestAuditRepositoryCommand:
    """
    Tests for the AuditRepository command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = AuditRepositoryCommand()
        
    def test_audit_repository_nonexistent_path(self):
        """Test auditing a path that doesn't exist"""
        result = self.command.execute(path="nonexistent_folder_xyz")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_audit_repository_rejects_file_path(self, tmp_path):
        """A file path must return a structured validation error, not raise."""
        candidate = tmp_path / "not-a-repository.txt"
        candidate.write_text("fixture", encoding="utf-8")

        result = self.command.execute(path=str(candidate))

        assert result["success"] is False
        assert result["error"] == f"Path '{candidate}' is not a directory."
        assert result["message"] == result["error"]

    def test_audit_repository_skips_gitignored_generated_files(self, tmp_path):
        """Git-aware audits must not waste findings on ignored build output."""
        subprocess.run(
            ["git", "init", "-q"],
            cwd=tmp_path,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        (tmp_path / "LICENSE").write_text("MIT License", encoding="utf-8")
        (tmp_path / ".gitignore").write_text(
            "node_modules\n.env\n__pycache__\ndist\nbuild\ntarget/\n",
            encoding="utf-8",
        )
        (tmp_path / "app.py").write_text("print('kept')\n", encoding="utf-8")
        generated = tmp_path / "native" / "project_languages" / "target"
        generated.mkdir(parents=True)
        (generated / "generated.py").write_text(
            "password = 'test_fixture_credential_value'\n",
            encoding="utf-8",
        )

        result = self.command.execute(path=str(tmp_path))

        assert result["success"] is True
        assert result["files_scanned"] == 3
        assert result["details"]["secrets"] == []
        assert all(
            "target" not in finding["path"]
            for finding in result["details"]["large_files"]
        )

    def test_audit_repository_reports_tracked_jar_as_binary(self, tmp_path):
        """Tracked Java archives are compiled artifacts and must be reported."""
        subprocess.run(
            ["git", "init", "-q"],
            cwd=tmp_path,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        (tmp_path / "LICENSE").write_text("MIT License", encoding="utf-8")
        (tmp_path / ".gitignore").write_text(
            "node_modules\n.env\n__pycache__\ndist\nbuild\n",
            encoding="utf-8",
        )
        (tmp_path / "fixture.jar").write_bytes(b"synthetic jar fixture")
        subprocess.run(
            ["git", "add", "LICENSE", ".gitignore", "fixture.jar"],
            cwd=tmp_path,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        result = self.command.execute(path=str(tmp_path))

        assert result["success"] is True
        assert result["details"]["binaries"] == ["fixture.jar"]

    def test_audit_repository_ignores_tracked_binary_deleted_from_worktree(
        self,
        tmp_path,
    ):
        subprocess.run(
            ["git", "init", "-q"],
            cwd=tmp_path,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        (tmp_path / "LICENSE").write_text("MIT License", encoding="utf-8")
        (tmp_path / ".gitignore").write_text(
            "node_modules\n.env\n__pycache__\ndist\nbuild\n",
            encoding="utf-8",
        )
        stale = tmp_path / "stale.exe"
        stale.write_bytes(b"tracked then removed")
        subprocess.run(
            ["git", "add", "LICENSE", ".gitignore", "stale.exe"],
            cwd=tmp_path,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stale.unlink()

        result = self.command.execute(path=str(tmp_path))

        assert result["success"] is True
        assert result["details"]["binaries"] == []
        assert all(
            finding["category"] != "binaries"
            for finding in result["details"]["summary"]["findings"]
        )

    def test_audit_repository_reports_hash_failures_as_incomplete(self, tmp_path):
        """Unreadable content must not produce a false successful audit."""
        (tmp_path / "LICENSE").write_text("MIT License", encoding="utf-8")
        (tmp_path / ".gitignore").write_text(
            "node_modules\n.env\n__pycache__\ndist\nbuild\n",
            encoding="utf-8",
        )
        (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")

        result = FailingHashAuditRepositoryCommand().execute(path=str(tmp_path))

        assert result["success"] is False
        assert result["analysis_complete"] is False
        assert result["error_code"] == "repository_scan_incomplete"
        assert result["files_scanned"] == 3
        assert any(
            issue["operation"] == "hash_file"
            and issue["path"] == "app.py"
            and "synthetic read failure" in issue["error"]
            for issue in result["scan_issues"]
        )

    def test_audit_repository_reports_file_limit_as_incomplete(self, tmp_path):
        """A bounded audit must expose truncation instead of claiming completion."""
        (tmp_path / "LICENSE").write_text("MIT License", encoding="utf-8")
        (tmp_path / ".gitignore").write_text(
            "node_modules\n.env\n__pycache__\ndist\nbuild\n",
            encoding="utf-8",
        )
        (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")

        result = TinyLimitAuditRepositoryCommand().execute(path=str(tmp_path))

        assert result["success"] is False
        assert result["analysis_complete"] is False
        assert result["files_scanned"] == 2
        assert result["scan_issues"] == [
            {
                "operation": "scan_limit",
                "error": (
                    "Repository scan stopped after 2 files."
                ),
                "limit": 2,
            }
        ]

class TestAuditRepositoryContentAndLinks:
    """Content, ignore, and documentation-link audit behavior."""

    def setup_method(self):
        self.command = AuditRepositoryCommand()

    def test_audit_repository_license_and_gitignore(self, tmp_path):
        """Test detection of missing LICENSE and .gitignore"""
        result = self.command.execute(path=str(tmp_path))
        assert result["success"] is True
        details = result["details"]
        assert details["license"] == "missing"
        
        # Check gitignore issues
        git_issues = [gi["issue"] for gi in details["gitignore_issues"]]
        assert "no_gitignore" in git_issues
        
        # Verify findings list has license and gitignore findings
        cats = [f["category"] for f in details["summary"]["findings"]]
        assert "license" in cats
        assert "gitignore" in cats
        
    def test_audit_repository_secrets_detection(self, tmp_path):
        """Test detection of hardcoded secrets in files"""
        # Create a mock code file with a secret
        code_file = tmp_path / "app.py"
        synthetic_google_key = "".join(
            ("AI", "za", "Sy", "FakeGoogleApiKey", "12345678901234567")
        )
        code_file.write_text(
            f"API_KEY = '{synthetic_google_key}'\n",
            encoding="utf-8",
        )
        
        # Create a LICENSE file
        license_file = tmp_path / "LICENSE"
        license_file.write_text("MIT License")
        
        # Create a .gitignore file
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules\n.env\n__pycache__\ndist\nbuild\n")
        
        result = self.command.execute(path=str(tmp_path))
        assert result["success"] is True
        details = result["details"]
        
        # Secret should be found
        assert len(details["secrets"]) >= 1
        assert any(s["file"] == "app.py" and "Google API Key" in s["type"] for s in details["secrets"])
        assert all("FakeGoogleApiKey" not in s["context"] for s in details["secrets"])
        
        # License should be found
        assert details["license"] == "LICENSE"
        
        # Gitignore should have no issues
        assert len(details["gitignore_issues"]) == 0
        
        # Risk level should be critical due to secret
        assert details["summary"]["risk_level"] == "critical"

    def test_audit_repository_does_not_treat_contact_uris_as_local_files(
        self, tmp_path
    ):
        """Non-file contact links are valid Markdown destinations, not paths."""
        (tmp_path / "LICENSE").write_text("MIT License", encoding="utf-8")
        (tmp_path / ".gitignore").write_text(
            "node_modules\n.env\n__pycache__\ndist\nbuild\n",
            encoding="utf-8",
        )
        (tmp_path / "README.md").write_text(
            "\n".join(
                (
                    "[Email](mailto:qzx@example.com)",
                    "[Telephone](tel:+15551234567)",
                    "[Chat](xmpp:qzx@example.com)",
                )
            ),
            encoding="utf-8",
        )

        result = self.command.execute(path=str(tmp_path))

        assert result["success"] is True
        assert result["details"]["broken_links"] == []

    def test_audit_repository_matches_placeholder_url_hostnames_exactly(
        self, tmp_path
    ):
        """Placeholder text outside the hostname must not suppress a check."""
        (tmp_path / "LICENSE").write_text("MIT License", encoding="utf-8")
        (tmp_path / ".gitignore").write_text(
            "node_modules\n.env\n__pycache__\ndist\nbuild\n",
            encoding="utf-8",
        )
        (tmp_path / "README.md").write_text(
            "\n".join(
                (
                    "[Reserved](https://example.com/guide)",
                    "[Reserved subdomain](https://docs.example.org/guide)",
                    "[Reserved TLD](https://service.test/guide)",
                    "[Reserved invalid](https://service.invalid/guide)",
                    "[Local](http://localhost/health)",
                    "[Loopback](http://127.0.0.1/health)",
                    "[Short loopback](http://127.1/health)",
                    "[Integer loopback](http://2130706433/health)",
                    "[Hex loopback](http://0x7f000001/health)",
                    "[IPv6 loopback](http://[::1]/health)",
                    "[Private literal](http://192.168.1.10/health)",
                    "[Lookalike](https://example.com.attacker.dev/guide)",
                    "[Query text](https://invalid.example.dev/?next=example.com)",
                    "[Local lookalike](https://localhost.attacker.dev/)",
                )
            ),
            encoding="utf-8",
        )

        command = RefusingNetworkAuditRepositoryCommand()
        result = command.execute(path=str(tmp_path))

        assert result["success"] is True
        assert command.requested_urls == [
            "https://example.com.attacker.dev/guide",
            "https://invalid.example.dev/?next=example.com",
            "https://localhost.attacker.dev/",
        ]
        assert [
            finding["link"] for finding in result["details"]["broken_links"]
        ] == command.requested_urls

    def test_repeated_external_links_are_checked_once_per_audit(self, tmp_path):
        (tmp_path / "LICENSE").write_text("MIT License", encoding="utf-8")
        (tmp_path / ".gitignore").write_text(
            "node_modules\n.env\n__pycache__\ndist\nbuild\n",
            encoding="utf-8",
        )
        repeated = "https://repeated.example.dev/health"
        (tmp_path / "README.md").write_text(
            f"[First]({repeated})\n",
            encoding="utf-8",
        )
        (tmp_path / "GUIDE.md").write_text(
            f"[Second]({repeated})\n",
            encoding="utf-8",
        )

        command = RefusingNetworkAuditRepositoryCommand()
        result = command.execute(path=str(tmp_path))

        assert result["success"] is True
        assert command.requested_urls == [repeated]
        findings = [
            item
            for item in result["details"]["broken_links"]
            if item["link"] == repeated
        ]
        assert sorted(item["file"] for item in findings) == [
            "GUIDE.md",
            "README.md",
        ]

    def test_external_link_checks_run_concurrently_and_keep_source_order(
        self,
        tmp_path,
    ):
        (tmp_path / "LICENSE").write_text("MIT License", encoding="utf-8")
        (tmp_path / ".gitignore").write_text(
            "node_modules\n.env\n__pycache__\ndist\nbuild\n",
            encoding="utf-8",
        )
        links = [
            f"https://parallel-{index}.example.dev/health"
            for index in range(4)
        ]
        (tmp_path / "README.md").write_text(
            "\n".join(
                f"[Link {index}]({link})"
                for index, link in enumerate(links)
            ),
            encoding="utf-8",
        )

        class ConcurrentNetworkAuditRepositoryCommand(AuditRepositoryCommand):
            def __init__(self):
                super().__init__()
                self.barrier = threading.Barrier(len(links))
                self.thread_ids = []

            def _open_url(self, request, timeout):
                assert timeout == 2.0
                self.thread_ids.append(threading.get_ident())
                self.barrier.wait(timeout=2)
                raise urllib.error.URLError(
                    f"synthetic unavailable: {request.full_url}"
                )

        command = ConcurrentNetworkAuditRepositoryCommand()
        result = command.execute(path=str(tmp_path))

        assert result["success"] is True
        assert len(set(command.thread_ids)) == len(links)
        assert [
            item["link"] for item in result["details"]["broken_links"]
        ] == links

    def test_unsafe_or_malformed_urls_do_not_abort_later_checks(self, tmp_path):
        """One hostile link must not hide later documentation findings."""
        credential_url = "".join(
            (
                "https://",
                "fixture-user",
                ":",
                "fixture-value",
                "@public.example.dev/path",
            )
        )
        (tmp_path / "LICENSE").write_text("MIT License", encoding="utf-8")
        (tmp_path / ".gitignore").write_text(
            "node_modules\n.env\n__pycache__\ndist\nbuild\n",
            encoding="utf-8",
        )
        (tmp_path / "README.md").write_text(
            "\n".join(
                (
                    f"[Credentials]({credential_url})",
                    "[Malformed](https://[::1)",
                    "[Later external](HTTPS://later.example.dev/path)",
                )
            ),
            encoding="utf-8",
        )

        command = RefusingNetworkAuditRepositoryCommand()
        result = command.execute(path=str(tmp_path))

        assert result["success"] is True
        assert command.requested_urls == ["HTTPS://later.example.dev/path"]
        broken_links = result["details"]["broken_links"]
        assert [finding["link"] for finding in broken_links] == [
            credential_url,
            "https://[::1",
            "HTTPS://later.example.dev/path",
        ]
        assert "Embedded URL credentials" in broken_links[0]["reason"]
        assert "Invalid URL" in broken_links[1]["reason"]
        assert "synthetic unavailable host" in broken_links[2]["reason"]

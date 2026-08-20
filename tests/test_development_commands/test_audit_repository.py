#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the AuditRepository command
"""

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

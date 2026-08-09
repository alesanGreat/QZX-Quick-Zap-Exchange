#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the consolidated, read-only diagnoseProject command."""

import json

from qzx.commands.development.diagnose_project import DiagnoseProjectCommand


class TestDiagnoseProjectCommand:
    """Exercise truthful discovery and evidence boundaries."""

    def setup_method(self):
        self.command = DiagnoseProjectCommand()

    def test_rejects_nonexistent_path(self):
        result = self.command.execute(path="nonexistent_folder_xyz")

        assert result["success"] is False
        assert "does not exist" in result["error"]

    def test_rejects_file_path(self, tmp_path):
        target = tmp_path / "file.txt"
        target.write_text("content", encoding="utf-8")

        result = self.command.execute(path=str(target))

        assert result["success"] is False
        assert "not a directory" in result["error"]

    def test_python_project_reports_real_manifests_and_partial_verification(
        self,
        tmp_path,
    ):
        (tmp_path / "pyproject.toml").write_text(
            "[build-system]\n"
            'requires = ["setuptools>=77", "wheel"]\n'
            'build-backend = "setuptools.build_meta"\n'
            "\n"
            "[project]\n"
            'name = "sample"\n'
            'dependencies = ["requests>=2", "packaging"]\n'
            "\n"
            "[project.optional-dependencies]\n"
            'test = ["pytest>=8"]\n'
            "\n"
            "[tool.pytest.ini_options]\n"
            'testpaths = ["tests"]\n'
            "\n"
            "[tool.ruff]\n"
            'target-version = "py313"\n',
            encoding="utf-8",
        )
        (tmp_path / "tests").mkdir()
        (tmp_path / ".pytest_cache").mkdir()

        result = self.command.execute(path=str(tmp_path))

        assert result["success"] is True
        details = result["details"]
        assert details["technologies"] == ["Python"]
        assert details["dependencies"]["unique_declared_package_count"] == 5
        manifest = details["dependencies"]["manifests"][0]
        assert manifest["group_counts"] == {
            "runtime": 2,
            "optional": 1,
            "build": 2,
        }
        assert details["validation"]["tests"]["status"] == "configured_not_run"
        assert details["validation"]["tests"]["configs"] == [
            "tests",
            "pyproject.toml [tool.pytest]",
        ]
        assert ".pytest_cache" not in details["validation"]["tests"]["configs"]
        assert details["validation"]["lint"]["tools"] == ["ruff"]
        verification = details["summary"]["verification"]
        assert verification["level"] == "partial"
        assert verification["release_readiness"] == "not_assessed"
        assert "tests" in verification["configured_but_not_run"]
        assert "health_score" not in details["summary"]

    def test_setup_py_dependencies_are_parsed_without_executing_setup(self, tmp_path):
        marker = tmp_path / "setup-executed.txt"
        (tmp_path / "setup.py").write_text(
            "from setuptools import setup\n"
            "install_requires = ['requests>=2', 'packaging']\n"
            "extras_require = {'test': ['pytest'], 'ai': ['requests']}\n"
            f"open({str(marker)!r}, 'w').write('executed')\n"
            "setup(name='sample', install_requires=install_requires, "
            "extras_require=extras_require)\n",
            encoding="utf-8",
        )

        result = self.command.execute(path=str(tmp_path))

        assert result["success"] is True
        manifest = result["details"]["dependencies"]["manifests"][0]
        assert manifest["path"] == "setup.py"
        assert manifest["group_counts"] == {"runtime": 2, "optional": 2}
        assert manifest["packages"] == ["packaging", "pytest", "requests"]
        assert not marker.exists()

    def test_package_scripts_are_discovered_but_never_executed(self, tmp_path):
        marker = tmp_path / "script-executed.txt"
        package = {
            "name": "read-only-check",
            "scripts": {
                "test": f'node -e "require(\'fs\').writeFileSync(\'{marker}\', \'test\')"',
                "lint": f'node -e "require(\'fs\').writeFileSync(\'{marker}\', \'lint\')"',
                "build": f'node -e "require(\'fs\').writeFileSync(\'{marker}\', \'build\')"',
            },
            "dependencies": {
                "@hotwired/turbo": "8.0.23",
                "web-vitals": "^5.1.0",
            },
            "devDependencies": {"vitest": "^3.0.0"},
        }
        (tmp_path / "package.json").write_text(
            json.dumps(package),
            encoding="utf-8",
        )
        (tmp_path / "pnpm-lock.yaml").touch()

        result = self.command.execute(path=str(tmp_path))

        assert result["success"] is True
        validation = result["details"]["validation"]
        assert validation["execution_policy"] == "discovery_only"
        assert validation["tests"]["tools"] == ["Vitest"]
        assert validation["tests"]["commands"] == ["pnpm run test"]
        assert validation["lint"]["commands"] == ["pnpm run lint"]
        assert validation["build"]["commands"] == ["pnpm run build"]
        assert result["details"]["dependencies"]["unique_packages"] == [
            "@hotwired/turbo",
            "vitest",
            "web-vitals",
        ]
        assert not marker.exists()

    def test_invalid_manifest_sections_are_ignored_without_execution(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps(
                {
                    "name": "invalid-sections",
                    "scripts": "npm test",
                    "dependencies": ["not", "a", "mapping"],
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / "composer.json").write_text(
            json.dumps({"require-dev": ["phpunit/phpunit"]}),
            encoding="utf-8",
        )

        result = self.command.execute(path=str(tmp_path))

        assert result["success"] is True
        validation = result["details"]["validation"]
        assert validation["tests"]["status"] == "not_configured"
        assert validation["lint"]["status"] == "not_configured"
        assert validation["build"]["status"] == "not_configured"

    def test_generated_sources_do_not_create_unused_code_candidates(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[project]\n"
            "name = 'test'\n",
            encoding="utf-8",
        )
        build = tmp_path / "build" / "lib"
        build.mkdir(parents=True)
        (build / "stale.py").write_text(
            "def stale_generated_function():\n"
            "    return 1\n",
            encoding="utf-8",
        )

        result = self.command.execute(path=str(tmp_path))

        assert result["success"] is True
        unused_code = result["details"]["source_analysis"]["unused_code"]
        assert unused_code["candidate_symbols_count"] == 0
        issue_codes = {
            issue["code"] for issue in result["details"]["summary"]["issues"]
        }
        assert "unused_code_candidates" not in issue_codes

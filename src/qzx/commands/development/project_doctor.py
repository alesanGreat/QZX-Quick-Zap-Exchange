#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Read-only project health diagnosis with explicit evidence boundaries."""

import ast
import json
import os
import re
import subprocess
import tomllib
from collections import Counter
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from qzx.commands.development.find_unused_code import FindUnusedCodeCommand
from qzx.commands.development.trace_circular_imports import (
    TraceCircularImportsCommand,
)
from qzx.core.command_base import CommandBase
from qzx.core.project_validation import inspect_validation_workflows
from qzx.core.recursive_findfiles_utils import (
    SOURCE_ANALYSIS_EXCLUDED_DIRECTORIES,
)


class ProjectDoctorCommand(CommandBase):
    """Inspect project health without executing project-owned scripts."""

    name = "projectDoctor"
    description = (
        "Inspects project technologies, dependencies, validation workflows, Git "
        "state, source quality, and large files without executing project scripts"
    )
    category = "development"

    parameters = [
        {
            "name": "path",
            "description": "Path to the project directory to diagnose (default: '.')",
            "required": False,
            "default": ".",
        }
    ]

    examples = [
        {
            "command": "qzx projectDoctor",
            "description": "Diagnose the current project without running its scripts",
        },
        {
            "command": "qzx projectDoctor C:/my/project",
            "description": "Diagnose the project at the specified path",
        },
    ]

    def execute(self, path="."):
        """Inspect a project and separate observations from unexecuted checks."""
        project_root = Path(path).expanduser().resolve()
        if not project_root.exists():
            return {
                "success": False,
                "error": f"Path '{path}' does not exist.",
                "message": f"Cannot diagnose the project because '{path}' does not exist.",
            }
        if not project_root.is_dir():
            return {
                "success": False,
                "error": f"Path '{path}' is not a directory.",
                "message": (
                    f"Cannot diagnose '{path}': projectDoctor requires a directory."
                ),
            }

        root_names = {entry.name for entry in project_root.iterdir()}
        pyproject = self._read_document(
            project_root / "pyproject.toml",
            tomllib.loads,
            (tomllib.TOMLDecodeError,),
        )
        package_json = self._read_document(
            project_root / "package.json",
            json.loads,
            (json.JSONDecodeError,),
        )
        composer_json = self._read_document(
            project_root / "composer.json",
            json.loads,
            (json.JSONDecodeError,),
        )

        technologies = self._detect_technologies(project_root, root_names)
        dependencies = self._inspect_dependencies(
            project_root,
            pyproject,
            package_json,
            composer_json,
        )
        environment = self._inspect_environment(root_names)
        validation = inspect_validation_workflows(
            project_root,
            root_names,
            technologies,
            pyproject,
            package_json,
            composer_json,
        )
        version_control = self._inspect_git(project_root)
        source_analysis = self._inspect_source(project_root)
        file_scan = self._scan_large_files(project_root)

        issues = self._build_issues(
            technologies=technologies,
            dependencies=dependencies,
            validation=validation,
            version_control=version_control,
            source_analysis=source_analysis,
            file_scan=file_scan,
        )
        summary = self._build_summary(issues, validation)

        issue_count = summary["issue_count"]
        pending_count = len(summary["verification"]["configured_but_not_run"])
        if issue_count:
            message = (
                f"Project diagnosis completed with {issue_count} observed "
                f"issue{'s' if issue_count != 1 else ''}."
            )
        else:
            message = "Project diagnosis completed with no observed issues."
        if pending_count:
            message += (
                f" {pending_count} configured validation "
                f"workflow{'s were' if pending_count != 1 else ' was'} discovered "
                "but not executed; run the suggested commands before treating the "
                "project as release-ready."
            )
        else:
            message += (
                " No executable validation workflow was discovered, so release "
                "readiness was not assessed."
            )

        return {
            "success": True,
            "message": message,
            "details": {
                "path": str(project_root),
                "technologies": technologies,
                "dependencies": dependencies,
                "environment": environment,
                "validation": validation,
                "version_control": version_control,
                "source_analysis": source_analysis,
                "file_scan": file_scan,
                "summary": summary,
            },
        }

    @staticmethod
    def _read_document(path, parser, parse_errors):
        if not path.is_file():
            return None
        try:
            return parser(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, *parse_errors) as exc:
            return {"_qzx_parse_error": str(exc)}

    @staticmethod
    def _detect_technologies(project_root, root_names):
        technologies = []
        if {
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "Pipfile",
        } & root_names or any(
            name.startswith("requirements") and name.endswith(".txt")
            for name in root_names
        ):
            technologies.append("Python")
        if "package.json" in root_names:
            technologies.append("Node.js")
        if "tsconfig.json" in root_names:
            technologies.append("TypeScript")
        if "Cargo.toml" in root_names:
            technologies.append("Rust")
        if "go.mod" in root_names:
            technologies.append("Go")
        if "composer.json" in root_names or any(
            entry.is_file() and entry.suffix.casefold() == ".php"
            for entry in project_root.iterdir()
        ):
            technologies.append("PHP")
        if {"CMakeLists.txt", "Makefile", "meson.build"} & root_names:
            technologies.append("C/C++")
        if {
            "Dockerfile",
            "compose.yml",
            "compose.yaml",
            "docker-compose.yml",
            "docker-compose.yaml",
        } & root_names:
            technologies.append("Docker")
        return technologies

    def _inspect_dependencies(
        self,
        project_root,
        pyproject,
        package_json,
        composer_json,
    ):
        manifests = []
        if (project_root / "pyproject.toml").is_file():
            manifests.append(self._parse_pyproject_dependencies(pyproject))
        if (project_root / "setup.py").is_file():
            manifests.append(self._parse_setup_dependencies(project_root / "setup.py"))
        for requirements_path in sorted(project_root.glob("requirements*.txt")):
            if requirements_path.is_file():
                manifests.append(
                    self._parse_requirements_dependencies(requirements_path)
                )
        if (project_root / "package.json").is_file():
            manifests.append(
                self._parse_mapping_dependency_groups(
                    "package.json",
                    "node",
                    package_json,
                    {
                        "runtime": "dependencies",
                        "development": "devDependencies",
                        "optional": "optionalDependencies",
                        "peer": "peerDependencies",
                    },
                )
            )
        if (project_root / "composer.json").is_file():
            manifests.append(
                self._parse_mapping_dependency_groups(
                    "composer.json",
                    "php",
                    composer_json,
                    {
                        "runtime": "require",
                        "development": "require-dev",
                    },
                )
            )
        if (project_root / "Cargo.toml").is_file():
            cargo = self._read_document(
                project_root / "Cargo.toml",
                tomllib.loads,
                (tomllib.TOMLDecodeError,),
            )
            manifests.append(
                self._parse_mapping_dependency_groups(
                    "Cargo.toml",
                    "rust",
                    cargo,
                    {
                        "runtime": "dependencies",
                        "development": "dev-dependencies",
                        "build": "build-dependencies",
                    },
                )
            )
        if (project_root / "go.mod").is_file():
            manifests.append(self._parse_go_mod(project_root / "go.mod"))

        unique_packages = {}
        parse_errors = []
        total_declarations = 0
        for manifest in manifests:
            total_declarations += manifest.get("declaration_count", 0)
            for package_name in manifest.get("packages", []):
                unique_packages.setdefault(
                    canonicalize_name(package_name),
                    package_name,
                )
            if manifest["status"] == "error":
                parse_errors.append(
                    {
                        "manifest": manifest["path"],
                        "error": manifest["error"],
                    }
                )

        return {
            "manifest_count": len(manifests),
            "manifests_found": [manifest["path"] for manifest in manifests],
            "total_declaration_count": total_declarations,
            "unique_declared_package_count": len(unique_packages),
            "unique_packages": sorted(unique_packages.values(), key=str.casefold),
            "parse_errors": parse_errors,
            "manifests": manifests,
            "counting_note": (
                "Declaration totals include repeated packages across manifests and "
                "dependency groups; unique_declared_package_count deduplicates "
                "normalized package names."
            ),
        }

    def _parse_pyproject_dependencies(self, data):
        if not isinstance(data, dict) or "_qzx_parse_error" in data:
            error = (
                data.get("_qzx_parse_error", "Invalid TOML document")
                if isinstance(data, dict)
                else "Invalid TOML document"
            )
            return self._dependency_record(
                "pyproject.toml",
                "python",
                error=error,
            )

        groups = {}
        project = data.get("project", {})
        if isinstance(project, dict):
            groups["runtime"] = project.get("dependencies", [])
            optional = project.get("optional-dependencies", {})
            if isinstance(optional, dict):
                groups["optional"] = [
                    requirement
                    for requirements in optional.values()
                    if isinstance(requirements, list)
                    for requirement in requirements
                ]
        build_system = data.get("build-system", {})
        if isinstance(build_system, dict):
            groups["build"] = build_system.get("requires", [])

        poetry = data.get("tool", {}).get("poetry", {})
        if isinstance(poetry, dict):
            poetry_runtime = poetry.get("dependencies", {})
            if isinstance(poetry_runtime, dict):
                groups.setdefault("runtime", [])
                groups["runtime"].extend(
                    name
                    for name in poetry_runtime
                    if name.casefold() != "python"
                )
            poetry_dev = poetry.get("dev-dependencies", {})
            if isinstance(poetry_dev, dict):
                groups.setdefault("development", [])
                groups["development"].extend(poetry_dev)
            poetry_groups = poetry.get("group", {})
            if isinstance(poetry_groups, dict):
                for group_name, group_data in poetry_groups.items():
                    dependencies = (
                        group_data.get("dependencies", {})
                        if isinstance(group_data, dict)
                        else {}
                    )
                    if isinstance(dependencies, dict):
                        scope = (
                            "development"
                            if group_name.casefold() in {"dev", "test", "lint"}
                            else "optional"
                        )
                        groups.setdefault(scope, [])
                        groups[scope].extend(dependencies)

        return self._dependency_record("pyproject.toml", "python", groups)

    def _parse_setup_dependencies(self, path):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            assignments = {}
            setup_call = None
            for node in tree.body:
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = (
                        node.targets
                        if isinstance(node, ast.Assign)
                        else [node.target]
                    )
                    value = node.value
                    for target in targets:
                        if isinstance(target, ast.Name):
                            try:
                                assignments[target.id] = ast.literal_eval(value)
                            except (ValueError, TypeError):
                                continue
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    function = node.value.func
                    if (
                        isinstance(function, ast.Name)
                        and function.id == "setup"
                        or isinstance(function, ast.Attribute)
                        and function.attr == "setup"
                    ):
                        setup_call = node.value

            groups = {}
            if setup_call is not None:
                keywords = {keyword.arg: keyword.value for keyword in setup_call.keywords}
                runtime = self._literal_or_assignment(
                    keywords.get("install_requires"),
                    assignments,
                )
                optional = self._literal_or_assignment(
                    keywords.get("extras_require"),
                    assignments,
                )
                if isinstance(runtime, (list, tuple, set)):
                    groups["runtime"] = list(runtime)
                if isinstance(optional, dict):
                    groups["optional"] = [
                        requirement
                        for requirements in optional.values()
                        if isinstance(requirements, (list, tuple, set))
                        for requirement in requirements
                    ]
            return self._dependency_record("setup.py", "python", groups)
        except (OSError, UnicodeError, SyntaxError) as exc:
            return self._dependency_record(
                "setup.py",
                "python",
                error=str(exc),
            )

    @staticmethod
    def _literal_or_assignment(node, assignments):
        if node is None:
            return None
        if isinstance(node, ast.Name):
            return assignments.get(node.id)
        try:
            return ast.literal_eval(node)
        except (ValueError, TypeError):
            return None

    def _parse_requirements_dependencies(self, path):
        try:
            requirements = []
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if (
                    not stripped
                    or stripped.startswith("#")
                    or stripped.startswith(("-r", "--requirement", "-c", "--constraint"))
                ):
                    continue
                requirements.append(stripped)
            return self._dependency_record(
                path.name,
                "python",
                {"runtime": requirements},
            )
        except (OSError, UnicodeError) as exc:
            return self._dependency_record(
                path.name,
                "python",
                error=str(exc),
            )

    def _parse_mapping_dependency_groups(
        self,
        path,
        ecosystem,
        data,
        group_keys,
    ):
        if not isinstance(data, dict) or "_qzx_parse_error" in data:
            error = (
                data.get("_qzx_parse_error", "Invalid dependency manifest")
                if isinstance(data, dict)
                else "Invalid dependency manifest"
            )
            return self._dependency_record(path, ecosystem, error=error)
        groups = {}
        for scope, key in group_keys.items():
            values = data.get(key, {})
            if isinstance(values, dict):
                groups[scope] = list(values)
        return self._dependency_record(path, ecosystem, groups)

    def _parse_go_mod(self, path):
        try:
            modules = []
            in_require_block = False
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.split("//", 1)[0].strip()
                if stripped == "require (":
                    in_require_block = True
                    continue
                if in_require_block and stripped == ")":
                    in_require_block = False
                    continue
                if stripped.startswith("require "):
                    stripped = stripped.removeprefix("require ").strip()
                elif not in_require_block:
                    continue
                if stripped:
                    modules.append(stripped.split()[0])
            return self._dependency_record(
                "go.mod",
                "go",
                {"runtime": modules},
            )
        except (OSError, UnicodeError) as exc:
            return self._dependency_record("go.mod", "go", error=str(exc))

    def _dependency_record(self, path, ecosystem, groups=None, error=None):
        if error is not None:
            return {
                "path": path,
                "ecosystem": ecosystem,
                "status": "error",
                "declaration_count": 0,
                "group_counts": {},
                "packages": [],
                "error": error,
            }

        normalized_groups = {}
        packages = {}
        for scope, values in (groups or {}).items():
            if not isinstance(values, (list, tuple, set)):
                continue
            names = []
            for value in values:
                name = self._dependency_name(value, ecosystem)
                if name:
                    names.append(name)
                    packages.setdefault(canonicalize_name(name), name)
            normalized_groups[scope] = names
        group_counts = {
            scope: len(values)
            for scope, values in normalized_groups.items()
            if values
        }
        return {
            "path": path,
            "ecosystem": ecosystem,
            "status": "parsed",
            "declaration_count": sum(group_counts.values()),
            "group_counts": group_counts,
            "packages": sorted(packages.values(), key=str.casefold),
        }

    @staticmethod
    def _dependency_name(value, ecosystem):
        if not isinstance(value, str):
            return None
        candidate = value.strip()
        if not candidate:
            return None
        if ecosystem in {"node", "php", "go", "rust"}:
            package_name = candidate.split()[0]
            if re.fullmatch(r"@?[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*", package_name):
                return package_name
        try:
            return Requirement(candidate).name
        except InvalidRequirement:
            match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", candidate)
            return match.group(0) if match else None

    @staticmethod
    def _inspect_environment(root_names):
        local_names = [
            name
            for name in (".env", ".env.local", ".env.development", ".env.test")
            if name in root_names
        ]
        template_names = [
            name
            for name in (".env.example", ".env.template", ".env.sample", "env.example")
            if name in root_names
        ]
        return {
            "local_files": local_names,
            "template_files": template_names,
            "local_configuration_present": bool(local_names),
            "template_present": bool(template_names),
            "values_inspected": False,
            "note": (
                "Only environment filenames are reported; projectDoctor never "
                "reads or returns environment values."
            ),
        }

    def _inspect_git(self, project_root):
        probe = self._run_git(project_root, "rev-parse", "--show-toplevel")
        if probe["status"] == "unavailable":
            return {
                "status": "unavailable",
                "reason": probe["error"],
            }
        if probe["status"] == "error":
            return {
                "status": "not_repository",
                "reason": "Git did not identify a repository for this path.",
            }

        repository_root = probe["stdout"]
        branch_result = self._run_git(
            project_root,
            "rev-parse",
            "--abbrev-ref",
            "HEAD",
        )
        status_result = self._run_git(
            project_root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        )
        status_lines = (
            status_result["stdout"].splitlines()
            if status_result["status"] == "ok"
            else []
        )
        untracked_count = sum(line.startswith("??") for line in status_lines)
        changed_count = len(status_lines) - untracked_count

        upstream_result = self._run_git(
            project_root,
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{upstream}",
        )
        upstream = (
            upstream_result["stdout"]
            if upstream_result["status"] == "ok"
            else None
        )
        commits_ahead = None
        commits_behind = None
        if upstream:
            divergence = self._run_git(
                project_root,
                "rev-list",
                "--left-right",
                "--count",
                f"HEAD...{upstream}",
            )
            if divergence["status"] == "ok":
                parts = divergence["stdout"].split()
                if len(parts) == 2 and all(part.isdigit() for part in parts):
                    commits_ahead = int(parts[0])
                    commits_behind = int(parts[1])

        branch = (
            branch_result["stdout"]
            if branch_result["status"] == "ok"
            else "unknown"
        )
        return {
            "status": "inspected",
            "repository_root": repository_root,
            "branch": branch,
            "detached_head": branch == "HEAD",
            "clean": not status_lines,
            "changed_count": changed_count,
            "untracked_count": untracked_count,
            "upstream": upstream,
            "commits_ahead": commits_ahead,
            "commits_behind": commits_behind,
        }

    @staticmethod
    def _run_git(project_root, *arguments):
        try:
            result = subprocess.run(
                ["git", *arguments],
                cwd=project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                check=False,
            )
        except FileNotFoundError:
            return {
                "status": "unavailable",
                "stdout": "",
                "error": "Git is not installed or is not available on PATH.",
            }
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "status": "unavailable",
                "stdout": "",
                "error": str(exc),
            }
        return {
            "status": "ok" if result.returncode == 0 else "error",
            "stdout": result.stdout.strip(),
            "error": result.stderr.strip(),
        }

    @staticmethod
    def _inspect_source(project_root):
        unused_result = FindUnusedCodeCommand().execute(scan_path=str(project_root))
        if unused_result.get("success"):
            unused_code = {
                "status": (
                    "attention"
                    if unused_result.get("candidate_symbols_count", 0)
                    else "passed"
                ),
                "candidate_symbols_count": unused_result.get(
                    "candidate_symbols_count",
                    0,
                ),
                "candidate_symbols": unused_result.get("candidate_symbols", [])[:10],
                "interpretation": (
                    "Candidates have no statically visible references; review dynamic "
                    "uses before removal."
                ),
            }
        else:
            unused_code = {
                "status": "error",
                "error": unused_result.get(
                    "message",
                    "Unused-code analysis failed without an explanation.",
                ),
            }

        circular_result = TraceCircularImportsCommand().execute(
            scan_path=str(project_root)
        )
        if circular_result.get("success"):
            circular_imports = {
                "status": (
                    "attention"
                    if circular_result.get("cycles_count", 0)
                    else "passed"
                ),
                "cycles_count": circular_result.get("cycles_count", 0),
                "cycles": circular_result.get("cycles", []),
            }
        else:
            circular_imports = {
                "status": "error",
                "error": circular_result.get(
                    "message",
                    "Circular-import analysis failed without an explanation.",
                ),
            }
        return {
            "unused_code": unused_code,
            "circular_imports": circular_imports,
        }

    def _scan_large_files(self, project_root):
        threshold_bytes = 1024 * 1024
        maximum_files = 5000
        excluded = {
            name.casefold()
            for name in SOURCE_ANALYSIS_EXCLUDED_DIRECTORIES
        } | {".git", ".dropbox", ".dropbox.cache", "artifacts"}
        large_files = []
        scanned_files = 0
        error_count = 0
        scan_complete = True

        for root, directories, files in os.walk(project_root):
            root_path = Path(root)
            directories[:] = [
                directory
                for directory in directories
                if directory.casefold() not in excluded
                and not (root_path / directory).is_symlink()
            ]
            for filename in files:
                if scanned_files >= maximum_files:
                    scan_complete = False
                    break
                scanned_files += 1
                file_path = root_path / filename
                try:
                    size_bytes = file_path.stat().st_size
                except OSError:
                    error_count += 1
                    continue
                if size_bytes > threshold_bytes:
                    large_files.append(
                        {
                            "path": str(file_path.relative_to(project_root)),
                            "size_bytes": size_bytes,
                            "size_formatted": self._format_bytes(size_bytes),
                        }
                    )
            if not scan_complete:
                break

        return {
            "scanned_file_count": scanned_files,
            "maximum_file_count": maximum_files,
            "scan_complete": scan_complete,
            "error_count": error_count,
            "large_file_threshold_bytes": threshold_bytes,
            "large_file_threshold_formatted": self._format_bytes(threshold_bytes),
            "large_file_count": len(large_files),
            "large_files": large_files,
        }

    @staticmethod
    def _build_issues(
        technologies,
        dependencies,
        validation,
        version_control,
        source_analysis,
        file_scan,
    ):
        issues = []

        def add(code, severity, title, description, remediation):
            issues.append(
                {
                    "code": code,
                    "severity": severity,
                    "title": title,
                    "description": description,
                    "remediation": remediation,
                }
            )

        if not technologies:
            add(
                "unknown_technology",
                "medium",
                "No supported project technology detected",
                "No conventional Python, Node.js, PHP, Rust, Go, C/C++, or Docker marker was found.",
                "Add the canonical manifest for the project or inspect the intended root directory.",
            )
        if dependencies["parse_errors"]:
            add(
                "dependency_manifest_parse_error",
                "medium",
                "One or more dependency manifests could not be parsed",
                f"{len(dependencies['parse_errors'])} manifest parse error(s) prevent a complete dependency inventory.",
                "Correct the reported manifest syntax and run projectDoctor again.",
            )
        if technologies and not validation["tests"]["configured"]:
            add(
                "tests_not_configured",
                "medium",
                "No test workflow detected",
                "The project technology was identified, but no conventional test folder, configuration, or script was found.",
                "Add a maintained test workflow appropriate for the detected technology.",
            )
        if version_control["status"] == "not_repository":
            add(
                "git_not_detected",
                "low",
                "Git repository not detected",
                "The inspected path is not inside a Git working tree.",
                "Use version control for maintained source projects or confirm that this directory is intentionally unversioned.",
            )
        elif version_control["status"] == "unavailable":
            add(
                "git_unavailable",
                "low",
                "Git state could not be inspected",
                version_control["reason"],
                "Install Git or make it available on PATH, then repeat the diagnosis.",
            )
        elif not version_control.get("clean", True):
            add(
                "git_worktree_changed",
                "info",
                "Git working tree has local changes",
                (
                    f"{version_control['changed_count']} tracked change(s) and "
                    f"{version_control['untracked_count']} untracked path(s) were observed."
                ),
                "Review the diff and untracked paths before a release or deployment.",
            )

        unused_code = source_analysis["unused_code"]
        if unused_code["status"] == "attention":
            add(
                "unused_code_candidates",
                "low",
                "Unused-code candidates require review",
                f"Static analysis found {unused_code['candidate_symbols_count']} definition(s) without visible references.",
                "Review dynamic imports and framework registration before removing any candidate.",
            )
        elif unused_code["status"] == "error":
            add(
                "unused_code_analysis_error",
                "medium",
                "Unused-code analysis failed",
                unused_code["error"],
                "Resolve the analysis error and repeat projectDoctor.",
            )

        circular_imports = source_analysis["circular_imports"]
        if circular_imports["status"] == "attention":
            add(
                "circular_imports",
                "medium",
                "Circular imports detected",
                f"Static analysis found {circular_imports['cycles_count']} circular dependency cycle(s).",
                "Move shared contracts to a lower-level module or invert the dependency.",
            )
        elif circular_imports["status"] == "error":
            add(
                "circular_import_analysis_error",
                "medium",
                "Circular-import analysis failed",
                circular_imports["error"],
                "Resolve the analysis error and repeat projectDoctor.",
            )

        if not file_scan["scan_complete"]:
            add(
                "file_scan_incomplete",
                "low",
                "File scan reached its safety limit",
                f"The scan stopped after {file_scan['maximum_file_count']} files.",
                "Inspect a narrower project root or use focused file commands for the remaining tree.",
            )
        if file_scan["error_count"]:
            add(
                "file_scan_errors",
                "low",
                "Some file metadata could not be read",
                f"{file_scan['error_count']} file metadata read(s) failed.",
                "Review permissions or transient file locks and repeat the scan.",
            )
        if file_scan["large_file_count"]:
            add(
                "large_files",
                "low",
                "Large files detected",
                f"{file_scan['large_file_count']} file(s) exceed {file_scan['large_file_threshold_formatted']}.",
                "Confirm each large file is intentional and appropriate for source, deployment, or project storage.",
            )

        return issues

    @staticmethod
    def _build_summary(issues, validation):
        severity_counts = Counter(issue["severity"] for issue in issues)
        material_issues = [
            issue for issue in issues if issue["severity"] != "info"
        ]
        if severity_counts["high"]:
            status = "critical"
        elif severity_counts["medium"]:
            status = "attention"
        elif severity_counts["low"]:
            status = "review"
        else:
            status = "no_issues_observed"

        configured_not_run = [
            name
            for name in ("tests", "lint", "type_checking", "build")
            if validation[name]["status"] == "configured_not_run"
        ]
        suggested_commands = list(
            dict.fromkeys(
                command
                for name in configured_not_run
                for command in validation[name]["commands"]
            )
        )
        verification_level = "partial" if configured_not_run else "limited"

        return {
            "status": status,
            "issue_count": len(material_issues),
            "informational_count": severity_counts["info"],
            "issue_counts_by_severity": {
                severity: severity_counts[severity]
                for severity in ("high", "medium", "low", "info")
            },
            "issues": issues,
            "verification": {
                "level": verification_level,
                "release_readiness": "not_assessed",
                "verified_areas": [
                    "technology and manifest discovery",
                    "dependency declaration inventory",
                    "Git working-tree state when Git is available",
                    "static unused-code candidates",
                    "static circular-import analysis",
                    "bounded large-file scan",
                ],
                "configured_but_not_run": configured_not_run,
                "suggested_commands": suggested_commands,
                "reason": (
                    "The command performs read-only inspection and never executes "
                    "project-owned validation or build scripts."
                ),
            },
        }

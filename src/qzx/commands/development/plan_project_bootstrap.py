#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Build a reviewable, read-only project bootstrap plan."""

import os
from pathlib import Path
import sys
from typing import ClassVar

from qzx.core.command_base import CommandBase


class PlanProjectBootstrapCommand(CommandBase):
    """Describe bootstrap work without writing files or running tools."""

    name = "planProjectBootstrap"
    aliases = []
    description = (
        "Builds a selectable project bootstrap plan without writing files, "
        "installing dependencies, creating secrets, or running migrations"
    )
    category = "development"

    result_schema: ClassVar[dict[str, object]] = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "message": {"type": "string"},
            "error": {"type": "string"},
            "error_code": {"type": "string"},
            "details": {
                "type": "object",
                "additionalProperties": True,
            },
        },
        "additionalProperties": True,
    }

    SUPPORTED_TECHNOLOGIES = (
        "python",
        "node",
        "typescript",
        "rust",
        "php",
        "cpp",
    )
    COMPONENTS = (
        "structure",
        "environment",
        "dependencies",
        "configuration",
        "hooks",
        "database",
        "checks",
    )
    STRUCTURE = {
        "python": ("src", "tests"),
        "node": ("src", "tests"),
        "typescript": ("src", "tests"),
        "rust": ("src", "tests"),
        "php": ("src", "tests"),
        "cpp": ("src", "include", "tests"),
    }
    SCAFFOLD_COMMANDS = {
        "python": "scaffoldPython",
        "node": "scaffoldJavascript",
        "typescript": "scaffoldTypescript",
        "rust": "scaffoldRust",
        "php": "scaffoldPhp",
        "cpp": "scaffoldCpp",
    }

    parameters = [
        {
            "name": "path",
            "description": "Project directory to inspect or plan",
            "required": False,
            "default": ".",
            "type": "str",
        },
        {
            "name": "tech",
            "description": (
                "Explicit stack: python, node, typescript, rust, php, or cpp. "
                "Required when manifests do not identify exactly one stack"
            ),
            "required": False,
            "default": None,
            "type": "str",
        },
        {
            "name": "components",
            "description": (
                "Comma-separated plan sections: structure, environment, "
                "dependencies, configuration, hooks, database, checks, or all"
            ),
            "required": False,
            "default": "all",
            "type": "str",
        },
    ]

    examples = [
        {
            "command": "qzx planProjectBootstrap . --tech python",
            "description": "Plan every Python bootstrap component without writes",
        },
        {
            "command": (
                "qzx planProjectBootstrap ./web --tech typescript "
                "--components structure,dependencies,checks"
            ),
            "description": "Plan selected TypeScript bootstrap components",
        },
        {
            "command": "qzx planProjectBootstrap ./existing-project",
            "description": "Detect one unambiguous stack from existing manifests",
        },
    ]

    def execute(self, path=".", tech=None, components="all"):
        try:
            target = Path(path).expanduser().resolve(strict=False)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return self._failure(
                "invalid_target",
                "{}: {}".format(type(exc).__name__, exc),
                "Choose a valid project directory path.",
                path,
            )
        if target.exists() and not target.is_dir():
            return self._failure(
                "target_not_directory",
                "Bootstrap target '{}' is not a directory.".format(target),
                "Choose a project directory or a path that does not exist yet.",
                target,
            )

        entries, read_error = self._root_entries(target)
        if read_error is not None:
            return self._failure(
                "target_not_readable",
                read_error,
                "Check directory permissions and retry.",
                target,
            )

        technology, detection = self._select_technology(tech, entries)
        if technology is None:
            error_code, error, message = detection
            return self._failure(
                error_code,
                error,
                message,
                target,
                detected_candidates=self._detect_technologies(entries),
                supported_technologies=list(self.SUPPORTED_TECHNOLOGIES),
            )

        selected_components, component_error = self._select_components(
            components
        )
        if component_error is not None:
            return self._failure(
                "invalid_components",
                component_error,
                (
                    "Choose a comma-separated subset or use 'all'. No files "
                    "or commands were changed."
                ),
                target,
                supported_components=list(self.COMPONENTS),
            )

        steps = []
        for component in selected_components:
            steps.extend(
                self._component_steps(
                    component,
                    technology,
                    target,
                    entries,
                )
            )

        manual_count = sum(
            step["status"] == "manual_review" for step in steps
        )
        would_create_count = sum(
            step["status"] == "would_create" for step in steps
        )
        network_count = sum(step["network"] for step in steps)
        sensitive_count = sum(step["sensitive"] for step in steps)
        filesystem_mutation_count = sum(
            step["mutates_files"] for step in steps
        )
        external_mutation_count = sum(
            step["mutates_external_state"] for step in steps
        )
        return {
            "success": True,
            "message": (
                "Prepared a read-only {} bootstrap plan for '{}' with {} "
                "selected components and {} steps. QZX executed no steps. "
                "Proposed effects: {} filesystem creations; {} manual-review "
                "steps; {} network-capable; {} sensitive; {} "
                "filesystem-mutating; {} external-state-mutating."
            ).format(
                technology,
                target,
                len(selected_components),
                len(steps),
                would_create_count,
                manual_count,
                network_count,
                sensitive_count,
                filesystem_mutation_count,
                external_mutation_count,
            ),
            "details": {
                "path": str(target),
                "path_exists": target.exists(),
                "technology": technology,
                "technology_selection": detection,
                "selected_components": selected_components,
                "steps": steps,
                "summary": {
                    "total_steps": len(steps),
                    "would_create": would_create_count,
                    "manual_review": manual_count,
                    "network_steps": network_count,
                    "sensitive_steps": sensitive_count,
                    "filesystem_mutating_steps": filesystem_mutation_count,
                    "externally_mutating_steps": external_mutation_count,
                    "executed_steps": 0,
                },
                "execution": {
                    "read_only": True,
                    "files_written": 0,
                    "commands_run": 0,
                    "network_requests": 0,
                    "secrets_generated": 0,
                },
                "recommended_scaffold_command": self.SCAFFOLD_COMMANDS[
                    technology
                ],
            },
        }

    @staticmethod
    def _root_entries(target):
        if not target.exists():
            return set(), None
        try:
            return {entry.name for entry in target.iterdir()}, None
        except OSError as exc:
            return set(), "{}: {}".format(type(exc).__name__, exc)

    @classmethod
    def _select_technology(cls, value, entries):
        candidates = cls._detect_technologies(entries)
        if value is not None and str(value).strip():
            technology = str(value).strip().lower()
            if technology not in cls.SUPPORTED_TECHNOLOGIES:
                return None, (
                    "unsupported_technology",
                    "Technology '{}' is not supported.".format(technology),
                    "Choose one exact supported technology; QZX made no guess.",
                )
            return technology, {
                "method": "explicit",
                "evidence": next(
                    (
                        item["evidence"]
                        for item in candidates
                        if item["technology"] == technology
                    ),
                    [],
                ),
                "observed_candidates": candidates,
            }

        if not candidates:
            return None, (
                "technology_required",
                "No supported technology manifest was found.",
                (
                    "Pass --tech explicitly. QZX does not silently default "
                    "an empty or unknown project to Python."
                ),
            )
        if len(candidates) > 1:
            return None, (
                "ambiguous_technology",
                "Multiple technology stacks were detected: {}.".format(
                    ", ".join(item["technology"] for item in candidates)
                ),
                "Pass --tech explicitly after reviewing the mixed repository.",
            )
        selected = candidates[0]
        return selected["technology"], {
            "method": "manifest",
            "evidence": selected["evidence"],
            "observed_candidates": candidates,
        }

    @staticmethod
    def _detect_technologies(entries):
        by_lower = {entry.lower(): entry for entry in entries}
        candidates = []

        def add(technology, names):
            evidence = [
                by_lower[name.lower()]
                for name in names
                if name.lower() in by_lower
            ]
            if evidence:
                candidates.append(
                    {
                        "technology": technology,
                        "evidence": sorted(evidence),
                    }
                )

        add("rust", ("Cargo.toml",))
        if "package.json" in by_lower:
            technology = (
                "typescript"
                if "tsconfig.json" in by_lower
                else "node"
            )
            evidence = [by_lower["package.json"]]
            if "tsconfig.json" in by_lower:
                evidence.append(by_lower["tsconfig.json"])
            candidates.append(
                {
                    "technology": technology,
                    "evidence": sorted(evidence),
                }
            )
        add("php", ("composer.json",))
        add("cpp", ("CMakeLists.txt", "Makefile"))
        add(
            "python",
            ("pyproject.toml", "requirements.txt", "setup.py"),
        )
        return sorted(candidates, key=lambda item: item["technology"])

    @classmethod
    def _select_components(cls, value):
        if value is None:
            return list(cls.COMPONENTS), None
        if isinstance(value, str):
            raw = [item.strip().lower() for item in value.split(",")]
        else:
            try:
                raw = [str(item).strip().lower() for item in value]
            except TypeError:
                return None, "components must be text or a sequence of names."
        requested = list(dict.fromkeys(item for item in raw if item))
        if requested == ["all"]:
            return list(cls.COMPONENTS), None
        if not requested:
            return None, "At least one bootstrap component is required."
        if "all" in requested:
            return None, "'all' cannot be combined with named components."
        unknown = sorted(set(requested) - set(cls.COMPONENTS))
        if unknown:
            return None, "Unknown bootstrap components: {}.".format(
                ", ".join(unknown)
            )
        return [
            component
            for component in cls.COMPONENTS
            if component in requested
        ], None

    @classmethod
    def _component_steps(cls, component, technology, target, entries):
        builders = {
            "structure": cls._structure_steps,
            "environment": cls._environment_steps,
            "dependencies": cls._dependency_steps,
            "configuration": cls._configuration_steps,
            "hooks": cls._hook_steps,
            "database": cls._database_steps,
            "checks": cls._check_steps,
        }
        return builders[component](technology, target, entries)

    @classmethod
    def _structure_steps(cls, technology, target, _entries):
        targets = [target]
        targets.extend(target / name for name in cls.STRUCTURE[technology])
        return [
            cls._step(
                "structure-{:02d}".format(index),
                "structure",
                "filesystem",
                "Create directory '{}' if the plan is approved.".format(path),
                "exists" if path.is_dir() else "would_create",
                target=path,
                mutates_files=not path.is_dir(),
            )
            for index, path in enumerate(targets, start=1)
        ]

    @classmethod
    def _environment_steps(cls, technology, target, entries):
        entries_lower = {entry.lower() for entry in entries}
        if technology == "python":
            exists = ".venv" in entries_lower
            command = (
                None
                if exists
                else [sys.executable, "-m", "venv", ".venv"]
            )
        else:
            manifests = {
                "node": {"package.json"},
                "typescript": {"package.json"},
                "rust": {"cargo.toml"},
                "php": {"composer.json"},
                "cpp": {"cmakelists.txt", "makefile"},
            }
            exists = bool(manifests[technology] & entries_lower)
            initializers = {
                "node": ["npm", "init", "-y"],
                "typescript": ["npm", "init", "-y"],
                "rust": ["cargo", "init"],
                "php": ["composer", "init"],
                "cpp": None,
            }
            command = None if exists else initializers[technology]
        return [
            cls._step(
                "environment-01",
                "environment",
                "native_command",
                (
                    "Review the existing project environment."
                    if exists
                    else "Review and run the stack initializer explicitly."
                ),
                "exists" if exists else "manual_review",
                argv=command,
                mutates_files=not exists,
            )
        ]

    @classmethod
    def _dependency_steps(cls, technology, target, entries):
        entries_lower = {entry.lower() for entry in entries}
        manifests = {
            "python": {
                "requirements.txt",
                "pyproject.toml",
                "setup.py",
            },
            "node": {"package.json"},
            "typescript": {"package.json"},
            "rust": {"Cargo.toml"},
            "php": {"composer.json"},
            "cpp": {"CMakeLists.txt", "Makefile"},
        }
        normalized_manifests = {
            name.lower() for name in manifests[technology]
        }
        present = sorted(normalized_manifests & entries_lower)
        command = None
        if present:
            if technology == "python":
                command = [
                    cls._venv_python(target),
                    "-m",
                    "pip",
                    "install",
                ]
                if "requirements.txt" in present:
                    command.extend(["-r", "requirements.txt"])
                else:
                    command.extend(["--editable", "."])
            elif technology in {"node", "typescript"}:
                command = ["npm", "install"]
            elif technology == "rust":
                command = ["cargo", "fetch"]
            elif technology == "php":
                command = ["composer", "install"]
            elif "cmakelists.txt" in present:
                command = ["cmake", "--build", "build"]
            else:
                command = ["make"]
        return [
            cls._step(
                "dependencies-01",
                "dependencies",
                "native_command",
                (
                    "Review dependency installation from {}.".format(
                        ", ".join(present)
                    )
                    if present
                    else "Define and review a dependency manifest first."
                ),
                "manual_review",
                argv=command,
                network=bool(present),
                mutates_files=bool(present),
                mutates_external_state=bool(present),
            )
        ]

    @classmethod
    def _configuration_steps(cls, _technology, target, entries):
        has_example = ".env.example" in entries
        return [
            cls._step(
                "configuration-01",
                "configuration",
                "sensitive_file",
                (
                    "Review .env.example and create .env manually without "
                    "committing secrets."
                    if has_example
                    else "Define an environment contract before creating .env."
                ),
                "manual_review",
                target=target / ".env",
                sensitive=True,
                mutates_files=True,
            )
        ]

    @classmethod
    def _hook_steps(cls, _technology, target, entries):
        return [
            cls._step(
                "hooks-01",
                "hooks",
                "repository_configuration",
                (
                    "Review the repository's existing hook policy."
                    if ".git" in entries
                    else "Initialize version control before choosing a hook policy."
                ),
                "manual_review",
                target=target / ".git" / "hooks",
                mutates_files=True,
            )
        ]

    @classmethod
    def _database_steps(cls, _technology, target, entries):
        command = None
        evidence = None
        if "manage.py" in entries:
            command = [
                cls._venv_python(target),
                "manage.py",
                "migrate",
            ]
            evidence = "manage.py"
        elif "artisan" in entries:
            command = ["php", "artisan", "migrate"]
            evidence = "artisan"
        elif "prisma" in {entry.lower() for entry in entries}:
            command = ["npx", "prisma", "migrate", "deploy"]
            evidence = "prisma"
        return [
            cls._step(
                "database-01",
                "database",
                "external_state",
                (
                    "Review database target, backup, and migration separately "
                    "before running the detected {} workflow.".format(evidence)
                    if command
                    else "No supported migration entry point was detected."
                ),
                "manual_review" if command else "not_detected",
                argv=command,
                network=bool(command),
                sensitive=bool(command),
                mutates_files=bool(command),
                mutates_external_state=bool(command),
            )
        ]

    @classmethod
    def _check_steps(cls, technology, target, _entries):
        commands = {
            "python": [cls._venv_python(target), "-m", "pytest"],
            "node": ["npm", "test"],
            "typescript": ["npm", "test"],
            "rust": ["cargo", "test"],
            "php": ["composer", "test"],
            "cpp": ["ctest", "--test-dir", "build"],
        }
        return [
            cls._step(
                "checks-01",
                "checks",
                "native_command",
                "Review and run the stack's initial checks explicitly.",
                "manual_review",
                argv=commands[technology],
                network=True,
                mutates_files=True,
                mutates_external_state=True,
            )
        ]

    @staticmethod
    def _venv_python(target):
        relative = (
            Path("Scripts") / "python.exe"
            if os.name == "nt"
            else Path("bin") / "python"
        )
        return str(target / ".venv" / relative)

    @staticmethod
    def _step(
        step_id,
        component,
        kind,
        description,
        status,
        *,
        target=None,
        argv=None,
        network=False,
        sensitive=False,
        mutates_files=False,
        mutates_external_state=False,
    ):
        step = {
            "id": step_id,
            "component": component,
            "kind": kind,
            "description": description,
            "status": status,
            "qzx_will_execute": False,
            "network": bool(network),
            "sensitive": bool(sensitive),
            "mutates_files": bool(mutates_files),
            "mutates_external_state": bool(mutates_external_state),
        }
        if target is not None:
            step["target"] = str(target)
        if argv is not None:
            step["argv"] = [str(value) for value in argv]
        return step

    @staticmethod
    def _failure(error_code, error, message, target, **details):
        payload = {
            "path": str(target),
            "read_only": True,
            "files_written": 0,
            "commands_run": 0,
            "network_requests": 0,
        }
        payload.update(details)
        return {
            "success": False,
            "error_code": error_code,
            "error": error,
            "message": message,
            "details": payload,
        }

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Compatibility wrapper for the former all-in-one bootstrap command."""

from qzx.commands.development.plan_project_bootstrap import (
    PlanProjectBootstrapCommand,
)


class BootstrapProjectCommand(PlanProjectBootstrapCommand):
    """Preserve read-only previews while refusing unsafe legacy execution."""

    name = "bootstrapProject"
    description = (
        "Deprecated compatibility preview for planProjectBootstrap; former "
        "live installation and migration behavior has been removed"
    )
    result_schema = {
        **PlanProjectBootstrapCommand.result_schema,
        "properties": {
            **PlanProjectBootstrapCommand.result_schema["properties"],
            "deprecated": {"type": "boolean"},
            "replacement": {"type": "string"},
            "supported_through": {"type": "string"},
        },
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
                "Explicit stack: python, node, typescript, rust, php, or cpp"
            ),
            "required": False,
            "default": None,
            "type": "str",
        },
        {
            "name": "dry_run",
            "description": (
                "Compatibility flag; only true is supported because this "
                "command no longer mutates projects"
            ),
            "required": False,
            "default": True,
            "type": "bool",
        },
        {
            "name": "components",
            "description": (
                "Comma-separated plan sections or all (default: all)"
            ),
            "required": False,
            "default": "all",
            "type": "str",
        },
    ]
    examples = [
        {
            "command": "qzx bootstrapProject . --tech python",
            "description": (
                "Preview a legacy invocation through planProjectBootstrap"
            ),
        },
        {
            "command": (
                "qzx bootstrapProject ./web --tech typescript "
                "--components structure,checks"
            ),
            "description": "Preview selected components during migration",
        },
    ]

    def execute(
        self,
        path=".",
        tech=None,
        dry_run=True,
        components="all",
    ):
        parsed_dry_run = self._parse_bool(dry_run)
        if parsed_dry_run is None:
            return self._deprecated_result(
                {
                    "success": False,
                    "error_code": "invalid_dry_run",
                    "error": "dry_run must be true or false.",
                    "message": (
                        "Use dry_run=true for the compatibility preview."
                    ),
                    "details": {
                        "read_only": True,
                        "files_written": 0,
                        "commands_run": 0,
                    },
                }
            )
        if not parsed_dry_run:
            return self._deprecated_result(
                {
                    "success": False,
                    "error_code": "unsafe_legacy_execution_removed",
                    "error": (
                        "The former live bootstrap mixed filesystem writes, "
                        "dependency installation, secret generation, hooks, "
                        "and database migrations in one operation."
                    ),
                    "message": (
                        "QZX made no changes. Use planProjectBootstrap, then "
                        "choose a stack-specific scaffold command and approve "
                        "installation, configuration, and migrations as "
                        "separate operations."
                    ),
                    "details": {
                        "path": str(path),
                        "read_only": True,
                        "files_written": 0,
                        "commands_run": 0,
                        "network_requests": 0,
                        "secrets_generated": 0,
                    },
                }
            )

        return self._deprecated_result(
            super().execute(
                path=path,
                tech=tech,
                components=components,
            )
        )

    @staticmethod
    def _deprecated_result(result):
        result["deprecated"] = True
        result["replacement"] = "planProjectBootstrap"
        result["supported_through"] = "QZX 0.2.x"
        result["message"] = (
            "bootstrapProject is deprecated; planProjectBootstrap is its "
            "read-only replacement. {}"
        ).format(result["message"])
        return result

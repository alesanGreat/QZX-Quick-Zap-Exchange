#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""QZX command base and stable public command API."""

from abc import ABC, abstractmethod
import os
import time

from qzx.core.command_arguments import (
    coerce_parameter_value,
    option_names,
    parse_bool,
    parse_command_arguments,
)
from qzx.core.command_invocation import invoke_command
from qzx.core.command_presentation import build_command_help, format_command_result


class CommandBase(ABC):
    """Abstract base class implemented by every public QZX command."""

    name = "base_command"
    description = "Base command"
    category = "misc"
    parameters = []
    examples = []

    # Commands may override this with an intentionally narrower JSON Schema.
    result_schema = None
    _byte_units = ("B", "KB", "MB", "GB", "TB")

    # High-risk commands opt in to an automatic pre-mutation safety backup.
    # The historic attribute name remains part of the public command contract.
    requires_explicit_approval = False
    approval_when_parameter = None
    backup_target_parameter = None

    # Variadic commands reject option-looking values by default. Commands that
    # deliberately transport another program's argv opt in.
    allow_variadic_option_passthrough = False
    approval_flags = {
        "--dangerously-bypass-approvals-and-sandbox",
        "--yolo",
    }

    @abstractmethod
    def execute(self, *args, **kwargs):
        """Execute the command and return its structured result."""
        pass

    def validate_parameters(self, args):
        """Return historic ``(is_valid, error)`` argument validation output."""
        is_valid, _, error = self.parse_arguments(args)
        return is_valid, error

    @staticmethod
    def _option_names(parameter):
        """Return all accepted long and explicit names for a parameter."""
        return option_names(parameter)

    @staticmethod
    def _parse_bool(value):
        """Parse a strict CLI boolean, returning ``None`` when unknown."""
        return parse_bool(value)

    def _format_bytes(self, bytes_value):
        """Format a byte count using QZX's historical 1024-based units."""
        final_unit = self._byte_units[-1]
        for unit in self._byte_units:
            if bytes_value < 1024 or unit == final_unit:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024

    def _coerce_parameter_value(self, parameter, value):
        """Convert CLI text using declared type or an unambiguous default."""
        return coerce_parameter_value(parameter, value, self._parse_bool)

    def _unknown_option_error(self, token, variadic_parameter):
        message = "Unknown option '{}' for {}.".format(token, self.name)
        if variadic_parameter is not None:
            message += (
                " Use '--' before a literal value beginning with '-' so typos "
                "remain distinguishable from data."
            )
        return self._usage_error(message)

    def parse_arguments(self, args):
        """Parse positional and named CLI arguments using command metadata."""
        return parse_command_arguments(self, args)

    def _usage_error(self, message):
        """Build a structured, actionable argument error."""
        usage_example = (
            self.examples[0].get("command")
            if self.examples
            else "qzx {} [parameters]".format(self.name)
        )
        return {
            "success": False,
            "error": message,
            "error_code": "usage_error",
            "message": "{} Usage: {}. Use 'qzx help {}' for details.".format(
                message, usage_example, self.name
            ),
            "details": {
                "command": self.name,
                "parameters": self.parameters,
            },
        }

    def get_safety_backup_target(self, values):
        """Return the declared filesystem path protected before mutation."""
        if self.backup_target_parameter:
            configured_target = values.get(self.backup_target_parameter)
            if configured_target not in {None, ""}:
                return configured_target
        return None

    def validate_safety_backup_target(self, target, values):
        """Return a structured preflight failure, or ``None`` when safe."""
        return None

    def _requested_high_risk_mutation(self, values):
        """Determine whether parsed values request an actual mutation."""
        parameter_names = {parameter.get("name") for parameter in self.parameters}
        has_dry_run = "dry_run" in parameter_names
        requested_mutation = (
            not bool(values.get("dry_run", False)) if has_dry_run else True
        )
        if self.approval_when_parameter:
            approval_value = values.get(self.approval_when_parameter, False)
            parsed_value = self._parse_bool(approval_value)
            requested_mutation = (
                parsed_value if parsed_value is not None else bool(approval_value)
            )
        if "apply" in parameter_names:
            requested_mutation = requested_mutation and bool(values.get("apply", False))
        return bool(requested_mutation)

    def get_maturity(self):
        """Return registry-backed maturity or an explicit extension override."""
        from qzx.core.command_lifecycle import (
            CommandLifecycleError,
            command_maturity,
            stage_maturity,
        )

        try:
            return command_maturity(self.name)
        except CommandLifecycleError:
            explicit_stage = self.__class__.__dict__.get("maturity")
            if explicit_stage is None:
                raise
            return stage_maturity(explicit_stage, "explicit_non_registry_command")

    def _finalize_invocation_result(self, raw_result, start, safety_backup=None):
        """Attach shared authoritative metadata to a known-command result."""
        result = self.format_result(raw_result)
        existing_meta = result.get("meta")
        if existing_meta is None:
            meta = {}
        elif isinstance(existing_meta, dict):
            meta = existing_meta
        else:
            meta = {"legacy_value": existing_meta}
        result["meta"] = meta
        meta["command"] = self.name
        meta["command_maturity"] = self.get_maturity()
        meta["duration_ms"] = round((time.perf_counter() - start) * 1000, 3)
        meta["schema_version"] = 1
        if safety_backup is not None:
            meta["safety_backup"] = safety_backup
            if safety_backup["status"] == "created":
                result["message"] = "{} Safety backup: '{}'.".format(
                    result["message"].rstrip(), safety_backup["path"]
                )
            elif safety_backup["status"] == "bypassed":
                result["message"] = "{} Safety backup was explicitly bypassed.".format(
                    result["message"].rstrip()
                )
        return result

    def invoke(self, args=None):
        """Parse, protect, execute, and normalize one command invocation."""
        return invoke_command(
            self,
            args,
            clock=time.perf_counter,
            environ=os.environ,
        )

    def get_help(self):
        """Return help text with description, parameters, examples, and safety."""
        return build_command_help(self)

    def format_result(self, result):
        """Normalize a producer value to the shared QZX result envelope."""
        return format_command_result(self, result)

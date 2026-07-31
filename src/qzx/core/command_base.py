#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX Command Base - Base class for all QZX commands
"""

from abc import ABC, abstractmethod
import os
import re
import time


class CommandBase(ABC):
    """
    Abstract base class that all commands must implement
    """
    
    # Command name (must be overridden by child classes)
    name = "base_command"
    
    # Brief command description
    description = "Base command"
    
    # Command category (file, system, dev, etc.)
    category = "misc"
    
    # Parameters accepted by the command with their descriptions
    parameters = []
    
    # Usage examples
    examples = []

    # Commands may override this with a JSON Schema when their output contract
    # is intentionally narrower than the shapes discoverable from their
    # top-level return dictionaries. Documentation generation always combines
    # it with QZX's shared ``success``/``message`` contract and validates any
    # captured evidence against the resulting schema.
    result_schema = None

    # Commands with narrower or wider historical display ranges may override
    # this tuple without reimplementing the conversion algorithm.
    _byte_units = ("B", "KB", "MB", "GB", "TB")

    # High-risk commands opt in to an automatic pre-mutation safety backup.
    # The historic attribute name remains part of the public command contract.
    requires_explicit_approval = False
    approval_when_parameter = None
    backup_target_parameter = None
    approval_flags = {
        "--dangerously-bypass-approvals-and-sandbox",
        "--yolo",
    }
    
    @abstractmethod
    def execute(self, *args, **kwargs):
        """
        Method that executes the command
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            The result of the command execution
        """
        pass
    
    def validate_parameters(self, args):
        """
        Validates if all required parameters are provided.
        
        Args:
            args: List of arguments passed to the command
            
        Returns:
            tuple: (is_valid, error_message)
                - is_valid: True if all required parameters are provided, False otherwise
                - error_message: Error message if validation fails, None otherwise
        """
        is_valid, _, error = self.parse_arguments(args)
        return is_valid, error

    @staticmethod
    def _option_names(parameter):
        """Return all accepted long and explicit option names for a parameter."""
        name = parameter.get("name", "")
        names = {
            "--{}".format(name),
            "--{}".format(name.replace("_", "-")),
        }
        names.update(parameter.get("flags", []))
        return {option.lower(): option for option in names if option}

    @staticmethod
    def _parse_bool(value):
        """Parse a strict CLI boolean, returning ``None`` for unknown values."""
        if isinstance(value, bool):
            return value
        if not isinstance(value, str):
            return None

        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "on", "t"}:
            return True
        if normalized in {"false", "no", "n", "0", "off", "f"}:
            return False
        return None

    def _format_bytes(self, bytes_value):
        """Format a byte count using QZX's historical 1024-based units."""
        final_unit = self._byte_units[-1]
        for unit in self._byte_units:
            if bytes_value < 1024 or unit == final_unit:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024

    def _coerce_parameter_value(self, parameter, value):
        """Convert CLI text using declared type or an unambiguous default."""
        if value is None or not isinstance(value, str):
            return value

        normalized = value.strip().lower()
        if normalized in {"null", "none"} and parameter.get("default") is None:
            return None

        declared_type = parameter.get("type")
        default = parameter.get("default")

        if declared_type in {"bool", bool} or isinstance(default, bool):
            parsed_bool = self._parse_bool(value)
            if parsed_bool is not None:
                return parsed_bool
            # Recursion has a deliberate boolean-or-depth domain. Preserve its
            # validated depth tokens for the command-specific normalizer.
            if parameter.get("name") == "recursive" and (
                re.fullmatch(r"(?:-r|--recursive)\d*", normalized)
                or re.fullmatch(r"\d+", normalized)
            ):
                return value
            raise ValueError(
                "expected true/false for '{}', received '{}'".format(
                    parameter.get("name", "parameter"),
                    value,
                )
            )

        target_type = declared_type
        if target_type is None and default is not None:
            if isinstance(default, int) and not isinstance(default, bool):
                target_type = int
            elif isinstance(default, float):
                target_type = float

        if target_type in {"int", int}:
            return int(value)
        if target_type in {"float", float}:
            return float(value)
        if target_type in {"str", str, None}:
            return value
        return value

    def parse_arguments(self, args):
        """
        Parse positional and named CLI arguments using command metadata.

        The parser preserves the historic positional interface while adding
        ``--name value``, ``--name=value``, ``--no-name`` and the common QZX
        recursion flags. It performs no command execution.
        """
        args = list(args or [])
        parameters = list(self.parameters or [])
        values = {}
        positionals = []
        option_map = {}
        approval_granted = False
        variadic_parameter = next(
            (p for p in parameters if p.get("is_variadic")),
            None,
        )

        for parameter in parameters:
            for option in self._option_names(parameter):
                option_map[option] = parameter

        # Common flags with one consistent meaning across the command catalog.
        shared_flags = {
            "-r": "recursive",
            "-R": "recursive",
            "--recursive": "recursive",
            "-i": "ignore_comments",
            "--ignore-comments": "ignore_comments",
            "--show_files_match": "show_files_match",
            "--show-files-match": "show_files_match",
        }

        index = 0
        passthrough = False
        while index < len(args):
            token = args[index]
            if passthrough:
                positionals.append(token)
                index += 1
                continue

            if token == "--":
                passthrough = True
                index += 1
                continue

            if token in self.approval_flags:
                if not self.requires_explicit_approval:
                    return False, None, self._usage_error(
                        "Approval flag '{}' is not applicable to {}.".format(
                            token,
                            self.name,
                        )
                    )
                approval_granted = True
                index += 1
                continue

            shared_name = shared_flags.get(token)
            recursion_depth = re.fullmatch(r"(?:-r|--recursive)(\d+)", token)
            if recursion_depth:
                shared_name = "recursive"

            if shared_name:
                parameter = next(
                    (p for p in parameters if p.get("name") == shared_name),
                    None,
                )
                if parameter is None:
                    if variadic_parameter is not None:
                        positionals.append(token)
                        index += 1
                        continue
                    return False, None, self._usage_error(
                        "Option '{}' is not supported by {}.".format(
                            token,
                            self.name,
                        )
                        )
                if shared_name == "recursive":
                    recursive_value = token
                    if recursion_depth is None and index + 1 < len(args):
                        candidate = args[index + 1]
                        parsed_candidate = self._parse_bool(candidate)
                        numeric_candidate = (
                            isinstance(candidate, str)
                            and re.fullmatch(r"[+-]?\d+", candidate.strip())
                        )
                        if parsed_candidate is not None:
                            recursive_value = parsed_candidate
                            index += 1
                        elif numeric_candidate:
                            recursive_value = int(candidate)
                            index += 1
                    values[shared_name] = recursive_value
                else:
                    values[shared_name] = True
                index += 1
                continue

            if isinstance(token, str) and token.startswith("--"):
                option_token, separator, inline_value = token.partition("=")
                normalized_option = option_token.lower()
                negated = normalized_option.startswith("--no-")
                lookup_option = (
                    "--" + normalized_option[5:]
                    if negated
                    else normalized_option
                )
                parameter = option_map.get(lookup_option)
                if parameter is None:
                    if variadic_parameter is not None:
                        positionals.append(token)
                        index += 1
                        continue
                    return False, None, self._usage_error(
                        "Unknown option '{}' for {}.".format(token, self.name)
                    )

                parameter_name = parameter["name"]
                if negated:
                    values[parameter_name] = False
                    index += 1
                    continue

                if separator:
                    raw_value = inline_value
                else:
                    next_value = args[index + 1] if index + 1 < len(args) else None
                    default = parameter.get("default")
                    is_bool = (
                        parameter.get("type") in {"bool", bool}
                        or isinstance(default, bool)
                    )
                    if next_value is None or (
                        isinstance(next_value, str)
                        and next_value.startswith("--")
                    ):
                        if is_bool:
                            raw_value = True
                        else:
                            return False, None, self._usage_error(
                                "Option '{}' requires a value.".format(token)
                            )
                    else:
                        raw_value = next_value
                        index += 1

                try:
                    converted_value = self._coerce_parameter_value(
                        parameter,
                        raw_value,
                    )
                    if parameter.get("is_variadic"):
                        values.setdefault(parameter_name, []).append(converted_value)
                    else:
                        values[parameter_name] = converted_value
                except (TypeError, ValueError) as exc:
                    return False, None, self._usage_error(str(exc))
                index += 1
                continue

            # Negative numeric values are positional values, not options.
            if (
                isinstance(token, str)
                and token.startswith("-")
                and not re.fullmatch(r"-\d+(?:\.\d+)?", token)
                and variadic_parameter is None
            ):
                return False, None, self._usage_error(
                    "Unknown option '{}' for {}.".format(token, self.name)
                )

            positionals.append(token)
            index += 1

        positional_index = 0
        for parameter in parameters:
            name = parameter.get("name")
            if parameter.get("is_variadic"):
                raw_values = positionals[positional_index:]
                try:
                    values[name] = list(values.get(name, [])) + [
                        self._coerce_parameter_value(parameter, item)
                        for item in raw_values
                    ]
                except (TypeError, ValueError) as exc:
                    return False, None, self._usage_error(str(exc))
                positional_index = len(positionals)
                continue
            if name in values:
                continue
            if positional_index < len(positionals):
                try:
                    values[name] = self._coerce_parameter_value(
                        parameter,
                        positionals[positional_index],
                    )
                except (TypeError, ValueError) as exc:
                    return False, None, self._usage_error(str(exc))
                positional_index += 1
            elif parameter.get("required", False):
                return False, None, self._usage_error(
                    "Missing required parameter: {}.".format(name)
                )
            elif "default" in parameter:
                values[name] = parameter.get("default")

        if positional_index < len(positionals):
            extras = positionals[positional_index:]
            return False, None, self._usage_error(
                "Too many arguments for {}: {}.".format(
                    self.name,
                    ", ".join(str(item) for item in extras),
                )
            )

        values["__qzx_approval_granted"] = approval_granted
        return True, values, None

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
                message,
                usage_example,
                self.name,
            ),
            "details": {
                "command": self.name,
                "parameters": self.parameters,
            },
        }

    def get_safety_backup_target(self, values):
        """
        Return the filesystem path protected before a dangerous mutation.

        Filesystem commands declare ``backup_target_parameter``. A dangerous
        operation without a restorable filesystem target must be explicitly
        authorized with one of the bypass flags.
        """
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
        parameter_names = {
            parameter.get("name")
            for parameter in self.parameters
        }
        has_dry_run = "dry_run" in parameter_names
        requested_mutation = (
            not bool(values.get("dry_run", False))
            if has_dry_run
            else True
        )
        if self.approval_when_parameter:
            approval_value = values.get(self.approval_when_parameter, False)
            parsed_approval_value = self._parse_bool(approval_value)
            requested_mutation = (
                parsed_approval_value
                if parsed_approval_value is not None
                else bool(approval_value)
            )
        if "apply" in parameter_names:
            requested_mutation = requested_mutation and bool(
                values.get("apply", False)
            )
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
            return stage_maturity(
                explicit_stage,
                "explicit_non_registry_command",
            )

    def _finalize_invocation_result(
        self,
        raw_result,
        start,
        safety_backup=None,
    ):
        """Attach the shared public metadata to every known-command result."""
        result = self.format_result(raw_result)
        existing_meta = result.get("meta")
        if existing_meta is None:
            meta = {}
        elif isinstance(existing_meta, dict):
            meta = existing_meta
        else:
            meta = {"legacy_value": existing_meta}
        result["meta"] = meta
        # Shared metadata is authoritative. Individual commands may add
        # namespaced metadata but cannot impersonate another command, maturity
        # assessment, schema, or execution duration.
        meta["command"] = self.name
        meta["command_maturity"] = self.get_maturity()
        meta["duration_ms"] = round(
            (time.perf_counter() - start) * 1000,
            3,
        )
        meta["schema_version"] = 1
        if safety_backup is not None:
            meta["safety_backup"] = safety_backup
            if safety_backup["status"] == "created":
                result["message"] = "{} Safety backup: '{}'.".format(
                    result["message"].rstrip(),
                    safety_backup["path"],
                )
            elif safety_backup["status"] == "bypassed":
                result["message"] = (
                    "{} Safety backup was explicitly bypassed."
                ).format(result["message"].rstrip())
        return result

    def invoke(self, args=None):
        """Parse, execute and normalize one command invocation."""
        start = time.perf_counter()
        valid, values, error = self.parse_arguments(args or [])
        if not valid:
            return self._finalize_invocation_result(error, start)

        flag_bypass_requested = values.pop(
            "__qzx_approval_granted",
            False,
        )
        environment_bypass_requested = (
            os.environ.get("QZX_SAFETY", "").strip().upper() == "YOLO"
        )
        bypass_requested = (
            flag_bypass_requested or environment_bypass_requested
        )
        bypass_reason = (
            "explicit_bypass_flag"
            if flag_bypass_requested
            else "QZX_SAFETY=YOLO"
        )
        parameter_names = {
            parameter.get("name")
            for parameter in self.parameters
        }
        safety_backup = None
        if self.requires_explicit_approval:
            has_dry_run = "dry_run" in parameter_names
            if bypass_requested:
                if "apply" in parameter_names:
                    values["apply"] = True
                if has_dry_run:
                    values["dry_run"] = False
            requested_mutation = self._requested_high_risk_mutation(values)

            if requested_mutation and bypass_requested:
                safety_backup = {
                    "status": "bypassed",
                    "reason": bypass_reason,
                    "command": self.name,
                }
            elif requested_mutation:
                backup_target = self.get_safety_backup_target(values)
                if backup_target is None:
                    return self._finalize_invocation_result({
                        "success": False,
                        "error_code": "approval_required",
                        "error": (
                            "This high-risk operation has no restorable "
                            "filesystem backup target."
                        ),
                        "message": (
                            "Review the operation, then add "
                            "--dangerously-bypass-approvals-and-sandbox "
                            "(or --yolo) to execute it."
                        ),
                        "details": {
                            "command": self.name,
                            "bypass_flags": sorted(self.approval_flags),
                        },
                    }, start)
                preflight_failure = self.validate_safety_backup_target(
                    backup_target,
                    values,
                )
                if preflight_failure is not None:
                    return self._finalize_invocation_result(
                        preflight_failure,
                        start,
                    )
                try:
                    from qzx.core.safety_backup import create_safety_backup

                    safety_backup = create_safety_backup(
                        self.name,
                        backup_target,
                    )
                except Exception as exc:
                    failed_backup = {
                        "status": "failed",
                        "target": str(backup_target),
                    }
                    return self._finalize_invocation_result({
                        "success": False,
                        "error_code": "safety_backup_failed",
                        "error": "{}: {}".format(
                            type(exc).__name__,
                            str(exc),
                        ),
                        "message": (
                            "Command '{}' was not executed because its required "
                            "safety backup could not be created: {}"
                        ).format(self.name, str(exc)),
                        "details": {
                            "command": self.name,
                            "backup_target": str(backup_target),
                            "bypass_flags": sorted(self.approval_flags),
                        },
                    }, start, safety_backup=failed_backup)
        try:
            variadic_parameter = next(
                (p for p in self.parameters if p.get("is_variadic")),
                None,
            )
            has_varargs = False
            if variadic_parameter is not None:
                import inspect

                signature = inspect.signature(self.execute)
                has_varargs = any(
                    parameter.kind == inspect.Parameter.VAR_POSITIONAL
                    for parameter in signature.parameters.values()
                )
            if has_varargs and variadic_parameter is not None:
                variadic_name = variadic_parameter["name"]
                variadic_values = values.get(variadic_name, [])
                positional_values = [
                    values[p["name"]]
                    for p in self.parameters
                    if not p.get("is_variadic") and p.get("name") in values
                ]
                raw_result = self.execute(*positional_values, *variadic_values)
            else:
                raw_result = self.execute(**values)
        except Exception as exc:
            raw_result = {
                "success": False,
                "error": "{}: {}".format(type(exc).__name__, str(exc)),
                "error_code": "command_execution_error",
                "message": "Command '{}' failed: {}".format(
                    self.name,
                    str(exc),
                ),
            }

        return self._finalize_invocation_result(
            raw_result,
            start,
            safety_backup=safety_backup,
        )
    
    def get_help(self):
        """
        Returns the command help
        
        Returns:
            str: Help text with description, parameters, and examples
        """
        maturity = self.get_maturity()
        help_text = [
            f"Command: {self.name}",
            f"Description: {self.description}",
            f"Maturity: {maturity['label']}",
            f"  {maturity['summary']}",
            ""
        ]
        
        # Add parameters
        if self.parameters:
            help_text.append("Parameters:")
            for param in self.parameters:
                param_name = param.get('name', 'unknown')
                description = param.get('description', '')
                required = param.get('required', False)
                default = param.get('default', None)
                
                required_text = "Required" if required else "Optional"
                default_text = f" (Default: {default})" if default is not None else ""
                
                help_text.append(f"  - {param_name}: {description} [{required_text}{default_text}]")
            help_text.append("")
        
        # Add examples
        if self.examples:
            help_text.append("Examples:")
            for example in self.examples:
                cmd = example.get('command', '')
                description = example.get('description', '')
                help_text.append(f"  {cmd}")
                if description:
                    help_text.append(f"    {description}")
            help_text.append("")

        if self.requires_explicit_approval:
            if self.backup_target_parameter:
                help_text.extend([
                    "High-risk safety:",
                    "  Preview or validation modes do not create a backup.",
                    "  Mutations create a safety backup before execution by default.",
                    "  --dangerously-bypass-approvals-and-sandbox (alias: --yolo) skips it.",
                    "  QZX_SAFETY=YOLO also skips it for all high-risk commands.",
                    "  Configure it with QZX_BACKUPS_PATH, QZX_BACKUPS_FORMAT,",
                    "  and QZX_BACKUPS_COMPRESSION.",
                    "",
                ])
            else:
                help_text.extend([
                    "High-risk safety:",
                    "  This operation has no restorable filesystem backup target.",
                    "  Execution requires --dangerously-bypass-approvals-and-sandbox",
                    "  its alias --yolo, or QZX_SAFETY=YOLO.",
                    "",
                ])
        
        return "\n".join(help_text)
    
    def format_result(self, result):
        """
        Ensures result is properly formatted with required fields
        
        Args:
            result: Result from the execute method
            
        Returns:
            dict: A properly formatted result dictionary with at least the 'message' field
        """
        # If result is already a dictionary
        if isinstance(result, dict):
            formatted = dict(result)
            if "success" not in formatted:
                status = str(formatted.get("status", "")).strip().lower()
                if status in {"success", "ok", "passed"}:
                    formatted["success"] = True
                elif status in {"error", "failed", "failure"}:
                    formatted["success"] = False
                else:
                    formatted["success"] = not bool(formatted.get("error"))

            formatted["success"] = bool(formatted["success"])

            if not formatted.get("message"):
                if formatted.get("error"):
                    formatted["message"] = str(formatted["error"])
                elif formatted["success"]:
                    formatted["message"] = (
                        "Command {} executed successfully.".format(self.name)
                    )
                else:
                    formatted["message"] = "Command {} failed.".format(self.name)

            formatted["message"] = str(formatted["message"])
            if not formatted["success"] and not formatted.get("error"):
                formatted["error"] = formatted["message"]
            return formatted
        
        message = str(result)
        looks_like_error = bool(
            re.match(
                r"^\s*(?:error|failed|failure|exception)\b",
                message,
                flags=re.IGNORECASE,
            )
        )
        formatted = {
            "success": not looks_like_error,
            "result": result,
            "message": message,
        }
        if looks_like_error:
            formatted["error"] = message
            formatted["error_code"] = "legacy_unstructured_error"
        else:
            formatted["warnings"] = [
                "Command returned a legacy unstructured value."
            ]
        return formatted

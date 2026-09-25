"""Metadata-driven parsing for public QZX command arguments."""

from __future__ import annotations

import re


SHARED_FLAGS = {
    "-r": "recursive",
    "-R": "recursive",
    "--recursive": "recursive",
    "-i": "ignore_comments",
    "--ignore-comments": "ignore_comments",
    "--show_files_match": "show_files_match",
    "--show-files-match": "show_files_match",
}


def option_names(parameter):
    """Return all accepted long and explicit names for one parameter."""
    name = parameter.get("name", "")
    names = {"--{}".format(name), "--{}".format(name.replace("_", "-"))}
    names.update(parameter.get("flags", []))
    return {option.lower(): option for option in names if option}


def parse_bool(value):
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


def coerce_parameter_value(parameter, value, parse_boolean=parse_bool):
    """Convert CLI text using declared type or an unambiguous default."""
    if value is None or not isinstance(value, str):
        return value
    normalized = value.strip().lower()
    if normalized in {"null", "none"} and parameter.get("default") is None:
        return None
    declared_type = parameter.get("type")
    default = parameter.get("default")
    if declared_type in {"bool", bool} or isinstance(default, bool):
        return _coerce_boolean(parameter, value, normalized, parse_boolean)
    target_type = _inferred_type(declared_type, default)
    if target_type in {"int", int}:
        return int(value)
    if target_type in {"float", float}:
        return float(value)
    return value


def _coerce_boolean(parameter, value, normalized, parse_boolean):
    parsed = parse_boolean(value)
    if parsed is not None:
        return parsed
    if parameter.get("name") == "recursive" and (
        re.fullmatch(r"(?:-r|--recursive)\d*", normalized)
        or re.fullmatch(r"\d+", normalized)
    ):
        return value
    raise ValueError(
        "expected true/false for '{}', received '{}'".format(
            parameter.get("name", "parameter"), value
        )
    )


def _inferred_type(declared_type, default):
    if declared_type is not None or default is None:
        return declared_type
    if isinstance(default, int) and not isinstance(default, bool):
        return int
    if isinstance(default, float):
        return float
    return None


class CommandArgumentParser:
    """Parse one command invocation while preserving metadata order."""

    def __init__(self, command, args):
        self.command = command
        self.args = list(args or [])
        self.parameters = list(command.parameters or [])
        self.values = {}
        self.positionals = []
        self.approval_granted = False
        self.variadic = next(
            (parameter for parameter in self.parameters if parameter.get("is_variadic")),
            None,
        )
        self.option_map = {
            option: parameter
            for parameter in self.parameters
            for option in command._option_names(parameter)
        }

    def parse(self):
        error = self._collect_tokens()
        if error is not None:
            return False, None, error
        error = self._assign_positionals()
        if error is not None:
            return False, None, error
        self.values["__qzx_approval_granted"] = self.approval_granted
        return True, self.values, None

    def _collect_tokens(self):
        index = 0
        passthrough = False
        while index < len(self.args):
            token = self.args[index]
            if passthrough:
                self.positionals.append(token)
                index += 1
                continue
            if token == "--":
                passthrough = True
                index += 1
                continue
            index, error = self._consume_token(index, token)
            if error is not None:
                return error
        return None

    def _consume_token(self, index, token):
        if token in self.command.approval_flags:
            return self._consume_approval(index, token)
        recursion_depth = re.fullmatch(r"(?:-r|--recursive)(\d+)", token)
        shared_name = "recursive" if recursion_depth else SHARED_FLAGS.get(token)
        if shared_name:
            return self._consume_shared(index, token, shared_name, recursion_depth)
        if isinstance(token, str) and token.startswith("--"):
            return self._consume_named(index, token)
        if self._is_unknown_short_option(token):
            return index, self.command._unknown_option_error(token, self.variadic)
        self.positionals.append(token)
        return index + 1, None

    def _consume_approval(self, index, token):
        if not self.command.requires_explicit_approval:
            return index, self.command._usage_error(
                "Approval flag '{}' is not applicable to {}.".format(
                    token, self.command.name
                )
            )
        self.approval_granted = True
        return index + 1, None

    def _parameter_named(self, name):
        return next(
            (parameter for parameter in self.parameters if parameter.get("name") == name),
            None,
        )

    def _consume_shared(self, index, token, shared_name, recursion_depth):
        parameter = self._parameter_named(shared_name)
        if parameter is None:
            if self.variadic is not None and self.command.allow_variadic_option_passthrough:
                self.positionals.append(token)
                return index + 1, None
            return index, self.command._unknown_option_error(token, self.variadic)
        if shared_name != "recursive":
            self.values[shared_name] = True
            return index + 1, None
        value, consumed_next = self._recursive_flag_value(index, token, recursion_depth)
        self.values[shared_name] = value
        return index + 1 + consumed_next, None

    def _recursive_flag_value(self, index, token, recursion_depth):
        if recursion_depth is not None or index + 1 >= len(self.args):
            return token, 0
        candidate = self.args[index + 1]
        parsed = self.command._parse_bool(candidate)
        if parsed is not None:
            return parsed, 1
        if isinstance(candidate, str) and re.fullmatch(r"[+-]?\d+", candidate.strip()):
            return int(candidate), 1
        return token, 0

    def _consume_named(self, index, token):
        option_token, separator, inline_value = token.partition("=")
        normalized = option_token.lower()
        negated = normalized.startswith("--no-")
        lookup = "--" + normalized[5:] if negated else normalized
        parameter = self.option_map.get(lookup)
        if parameter is None:
            return self._unknown_named_option(index, token)
        if negated:
            self.values[parameter["name"]] = False
            return index + 1, None
        raw_value, consumed_next, error = self._named_raw_value(
            index, token, parameter, separator, inline_value
        )
        if error is not None:
            return index, error
        return self._store_named_value(index, parameter, raw_value, consumed_next)

    def _unknown_named_option(self, index, token):
        if self.variadic is not None and self.command.allow_variadic_option_passthrough:
            self.positionals.append(token)
            return index + 1, None
        return index, self.command._unknown_option_error(token, self.variadic)

    def _named_raw_value(self, index, token, parameter, separator, inline_value):
        if separator:
            return inline_value, 0, None
        next_value = self.args[index + 1] if index + 1 < len(self.args) else None
        default = parameter.get("default")
        is_bool = parameter.get("type") in {"bool", bool} or isinstance(default, bool)
        missing = next_value is None or (
            isinstance(next_value, str) and next_value.startswith("--")
        )
        if missing and is_bool:
            return True, 0, None
        if missing:
            return None, 0, self.command._usage_error(
                "Option '{}' requires a value.".format(token)
            )
        return next_value, 1, None

    def _store_named_value(self, index, parameter, raw_value, consumed_next):
        try:
            converted = self.command._coerce_parameter_value(parameter, raw_value)
        except (TypeError, ValueError) as exc:
            return index, self.command._usage_error(str(exc))
        name = parameter["name"]
        if parameter.get("is_variadic"):
            self.values.setdefault(name, []).append(converted)
        else:
            self.values[name] = converted
        return index + 1 + consumed_next, None

    def _is_unknown_short_option(self, token):
        return (
            isinstance(token, str)
            and token.startswith("-")
            and not re.fullmatch(r"-\d+(?:\.\d+)?", token)
            and not (
                self.variadic is not None
                and self.command.allow_variadic_option_passthrough
            )
        )

    def _assign_positionals(self):
        positional_index = 0
        for parameter in self.parameters:
            positional_index, error = self._assign_parameter(parameter, positional_index)
            if error is not None:
                return error
        if positional_index < len(self.positionals):
            extras = self.positionals[positional_index:]
            return self.command._usage_error(
                "Too many arguments for {}: {}.".format(
                    self.command.name, ", ".join(str(item) for item in extras)
                )
            )
        return None

    def _assign_parameter(self, parameter, positional_index):
        name = parameter.get("name")
        if parameter.get("is_variadic"):
            return self._assign_variadic(parameter, name, positional_index)
        if name in self.values:
            return positional_index, None
        if positional_index < len(self.positionals):
            return self._assign_positional(parameter, name, positional_index)
        if parameter.get("required", False):
            return positional_index, self.command._usage_error(
                "Missing required parameter: {}.".format(name)
            )
        if "default" in parameter:
            self.values[name] = parameter.get("default")
        return positional_index, None

    def _assign_variadic(self, parameter, name, positional_index):
        try:
            trailing = [
                self.command._coerce_parameter_value(parameter, item)
                for item in self.positionals[positional_index:]
            ]
        except (TypeError, ValueError) as exc:
            return positional_index, self.command._usage_error(str(exc))
        self.values[name] = list(self.values.get(name, [])) + trailing
        return len(self.positionals), None

    def _assign_positional(self, parameter, name, positional_index):
        try:
            self.values[name] = self.command._coerce_parameter_value(
                parameter, self.positionals[positional_index]
            )
        except (TypeError, ValueError) as exc:
            return positional_index, self.command._usage_error(str(exc))
        return positional_index + 1, None


def parse_command_arguments(command, args):
    """Parse positional and named values for one QZX command."""
    return CommandArgumentParser(command, args).parse()

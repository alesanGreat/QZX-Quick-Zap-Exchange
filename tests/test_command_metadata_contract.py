"""Catalog-wide invariants between public metadata and Python call signatures."""

from __future__ import annotations

import inspect
import re

from qzx.core.command_loader import CommandLoader


_PARAMETER_NAME = re.compile(r"[a-z][a-z0-9_]*\Z")
_ALLOWED_PARAMETER_TYPES = {None, "str", "int", "float", "bool", str, int, float, bool}


def _catalog_contract_violations():
    loader = CommandLoader()
    registered = loader.discover_commands()
    violations = []
    for command_class in sorted(
        set(registered.values()),
        key=lambda candidate: candidate.name.casefold(),
    ):
        violations.extend(_command_contract_violations(command_class))
    return loader, violations


def _command_contract_violations(command_class):
    command_name = command_class.name
    parameters = command_class.parameters
    violations = _command_identity_violations(command_class)
    if not isinstance(parameters, list):
        violations.append(f"{command_name}: parameters must be a list")
        return violations

    (
        parameter_violations,
        valid_parameters,
        seen_names,
        variadic_parameters,
    ) = _parameter_contract(command_name, parameters)
    violations.extend(parameter_violations)
    violations.extend(
        _variadic_contract_violations(
            command_class,
            parameters,
            variadic_parameters,
        )
    )
    violations.extend(
        _signature_contract_violations(
            command_class,
            valid_parameters,
            variadic_parameters,
        )
    )
    violations.extend(
        _safety_reference_violations(command_class, seen_names)
    )
    violations.extend(_example_contract_violations(command_class))
    return violations


def _command_identity_violations(command_class):
    violations = []
    if (
        not isinstance(command_class.description, str)
        or not command_class.description.strip()
    ):
        violations.append(
            f"{command_class.name}: description must be non-empty text"
        )
    if (
        not isinstance(command_class.category, str)
        or not command_class.category.strip()
    ):
        violations.append(
            f"{command_class.name}: category must be non-empty text"
        )
    return violations


def _parameter_contract(command_name, parameters):
    violations = []
    seen_names = set()
    variadic_parameters = []
    valid_parameters = []
    for index, parameter in enumerate(parameters):
        if not isinstance(parameter, dict):
            violations.append(
                f"{command_name}: parameter {index} must be an object"
            )
            continue
        name = parameter.get("name")
        if (
            not isinstance(name, str)
            or not _PARAMETER_NAME.fullmatch(name)
        ):
            violations.append(
                f"{command_name}: invalid parameter name {name!r}"
            )
            continue
        if name in seen_names:
            violations.append(
                f"{command_name}: duplicate parameter {name!r}"
            )
        seen_names.add(name)
        valid_parameters.append(parameter)
        violations.extend(
            _parameter_field_violations(command_name, name, parameter)
        )
        if parameter.get("is_variadic"):
            variadic_parameters.append((index, name))
    return violations, valid_parameters, seen_names, variadic_parameters


def _parameter_field_violations(command_name, name, parameter):
    violations = []
    description = parameter.get("description")
    if not isinstance(description, str) or not description.strip():
        violations.append(
            f"{command_name}.{name}: description is required"
        )
    if parameter.get("required", False) not in {True, False}:
        violations.append(
            f"{command_name}.{name}: required must be boolean"
        )
    if parameter.get("is_variadic", False) not in {True, False}:
        violations.append(
            f"{command_name}.{name}: is_variadic must be boolean"
        )
    if parameter.get("type") not in _ALLOWED_PARAMETER_TYPES:
        violations.append(
            f"{command_name}.{name}: unsupported type "
            f"{parameter.get('type')!r}"
        )
    if parameter.get("required") and "default" in parameter:
        violations.append(
            f"{command_name}.{name}: a required parameter cannot publish "
            "a default"
        )
    return violations


def _variadic_contract_violations(
    command_class,
    parameters,
    variadic_parameters,
):
    command_name = command_class.name
    violations = []
    if len(variadic_parameters) > 1:
        violations.append(
            f"{command_name}: only one variadic parameter is allowed"
        )
    passthrough = getattr(
        command_class,
        "allow_variadic_option_passthrough",
        False,
    )
    if not isinstance(passthrough, bool):
        violations.append(
            f"{command_name}: allow_variadic_option_passthrough must be boolean"
        )
    if passthrough and not variadic_parameters:
        violations.append(
            f"{command_name}: option passthrough requires a variadic parameter"
        )
    if (
        variadic_parameters
        and variadic_parameters[0][0] != len(parameters) - 1
    ):
        violations.append(
            f"{command_name}.{variadic_parameters[0][1]}: variadic parameter "
            "must be last"
        )
    return violations


def _signature_contract_violations(
    command_class,
    valid_parameters,
    variadic_parameters,
):
    (
        named_signature_parameters,
        has_varargs,
        has_varkw,
    ) = _execute_signature(command_class)
    metadata_parameters = {
        parameter["name"]: parameter
        for parameter in valid_parameters
        if not parameter.get("is_variadic")
    }
    violations = _signature_name_violations(
        command_class.name,
        metadata_parameters,
        named_signature_parameters,
        variadic_parameters,
        has_varargs,
        has_varkw,
    )
    violations.extend(
        _signature_default_violations(
            command_class.name,
            metadata_parameters,
            named_signature_parameters,
        )
    )
    return violations


def _execute_signature(command_class):
    signature = inspect.signature(command_class.execute)
    parameters = {
        name: parameter
        for name, parameter in signature.parameters.items()
        if name != "self"
    }
    named = {
        name: parameter
        for name, parameter in parameters.items()
        if parameter.kind
        not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        )
    }
    has_varargs = any(
        parameter.kind == inspect.Parameter.VAR_POSITIONAL
        for parameter in parameters.values()
    )
    has_varkw = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
    return named, has_varargs, has_varkw


def _signature_name_violations(
    command_name,
    metadata_parameters,
    signature_parameters,
    variadic_parameters,
    has_varargs,
    has_varkw,
):
    violations = []
    if bool(variadic_parameters) != has_varargs:
        violations.append(
            f"{command_name}: metadata variadic={bool(variadic_parameters)} "
            f"but execute varargs={has_varargs}"
        )
    for name in sorted(set(metadata_parameters) - set(signature_parameters)):
        if not has_varkw:
            violations.append(
                f"{command_name}.{name}: documented but not accepted by execute"
            )
    for name in sorted(set(signature_parameters) - set(metadata_parameters)):
        violations.append(
            f"{command_name}.{name}: accepted by execute but missing from metadata"
        )
    return violations


def _signature_default_violations(
    command_name,
    metadata_parameters,
    signature_parameters,
):
    violations = []
    for name, metadata in metadata_parameters.items():
        signature_parameter = signature_parameters.get(name)
        if signature_parameter is None:
            continue
        required = signature_parameter.default is inspect.Parameter.empty
        if bool(metadata.get("required", False)) != required:
            violations.append(
                f"{command_name}.{name}: required metadata disagrees with execute"
            )
        if (
            "default" in metadata
            and not required
            and signature_parameter.default is not None
            and metadata["default"] != signature_parameter.default
        ):
            violations.append(
                f"{command_name}.{name}: public default "
                f"{metadata['default']!r} disagrees with execute default "
                f"{signature_parameter.default!r}"
            )
        if (
            "default" not in metadata
            and not required
            and signature_parameter.default is not None
        ):
            violations.append(
                f"{command_name}.{name}: execute default "
                f"{signature_parameter.default!r} is undocumented"
            )
    return violations


def _safety_reference_violations(command_class, seen_names):
    violations = []
    for attribute in (
        "approval_when_parameter",
        "backup_target_parameter",
    ):
        target = getattr(command_class, attribute, None)
        if target and target not in seen_names:
            violations.append(
                f"{command_class.name}: {attribute} refers to missing "
                f"parameter {target!r}"
            )
    return violations


def _example_contract_violations(command_class):
    examples = command_class.examples
    if not isinstance(examples, list) or not examples:
        return [
            f"{command_class.name}: at least one example is required"
        ]
    prefix = f"qzx {command_class.name}"
    if any(
        isinstance(example, dict)
        and isinstance(example.get("command"), str)
        and (
            example["command"] == prefix
            or example["command"].startswith(prefix + " ")
        )
        for example in examples
    ):
        return []
    return [
        f"{command_class.name}: examples need one canonical invocation "
        f"beginning with {prefix!r}"
    ]


def test_command_catalog_metadata_matches_public_execute_signatures():
    loader, violations = _catalog_contract_violations()

    assert loader.load_errors == {}
    assert loader.registration_warnings == []
    assert violations == [], (
        "Command metadata is executable API, not descriptive decoration:\n"
        + "\n".join(violations)
    )

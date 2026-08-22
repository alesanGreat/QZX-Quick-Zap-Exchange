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
        command_name = command_class.name
        parameters = command_class.parameters

        if not isinstance(command_class.description, str) or not command_class.description.strip():
            violations.append(f"{command_name}: description must be non-empty text")
        if not isinstance(command_class.category, str) or not command_class.category.strip():
            violations.append(f"{command_name}: category must be non-empty text")
        if not isinstance(parameters, list):
            violations.append(f"{command_name}: parameters must be a list")
            continue

        seen_names = set()
        variadic_parameters = []
        valid_parameters = []
        for index, parameter in enumerate(parameters):
            if not isinstance(parameter, dict):
                violations.append(
                    f"{command_name}: parameter {index} must be an object"
                )
                continue

            parameter_name = parameter.get("name")
            if not isinstance(parameter_name, str) or not _PARAMETER_NAME.fullmatch(
                parameter_name
            ):
                violations.append(
                    f"{command_name}: invalid parameter name {parameter_name!r}"
                )
                continue
            if parameter_name in seen_names:
                violations.append(
                    f"{command_name}: duplicate parameter {parameter_name!r}"
                )
            seen_names.add(parameter_name)
            valid_parameters.append(parameter)

            description = parameter.get("description")
            if not isinstance(description, str) or not description.strip():
                violations.append(
                    f"{command_name}.{parameter_name}: description is required"
                )
            if parameter.get("required", False) not in {True, False}:
                violations.append(
                    f"{command_name}.{parameter_name}: required must be boolean"
                )
            if parameter.get("is_variadic", False) not in {True, False}:
                violations.append(
                    f"{command_name}.{parameter_name}: is_variadic must be boolean"
                )
            if parameter.get("type") not in _ALLOWED_PARAMETER_TYPES:
                violations.append(
                    f"{command_name}.{parameter_name}: unsupported type "
                    f"{parameter.get('type')!r}"
                )
            if parameter.get("required") and "default" in parameter:
                violations.append(
                    f"{command_name}.{parameter_name}: a required parameter cannot "
                    "publish a default"
                )
            if parameter.get("is_variadic"):
                variadic_parameters.append((index, parameter_name))

        if len(variadic_parameters) > 1:
            violations.append(f"{command_name}: only one variadic parameter is allowed")
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
        if variadic_parameters and variadic_parameters[0][0] != len(parameters) - 1:
            violations.append(
                f"{command_name}.{variadic_parameters[0][1]}: variadic parameter "
                "must be last"
            )

        signature = inspect.signature(command_class.execute)
        signature_parameters = {
            name: parameter
            for name, parameter in signature.parameters.items()
            if name != "self"
        }
        named_signature_parameters = {
            name: parameter
            for name, parameter in signature_parameters.items()
            if parameter.kind
            not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        }
        has_varargs = any(
            parameter.kind == inspect.Parameter.VAR_POSITIONAL
            for parameter in signature_parameters.values()
        )
        has_varkw = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature_parameters.values()
        )
        metadata_parameters = {
            parameter["name"]: parameter
            for parameter in valid_parameters
            if not parameter.get("is_variadic")
        }

        if bool(variadic_parameters) != has_varargs:
            violations.append(
                f"{command_name}: metadata variadic={bool(variadic_parameters)} "
                f"but execute varargs={has_varargs}"
            )
        for parameter_name in sorted(
            set(metadata_parameters) - set(named_signature_parameters)
        ):
            if not has_varkw:
                violations.append(
                    f"{command_name}.{parameter_name}: documented but not accepted "
                    "by execute"
                )
        for parameter_name in sorted(
            set(named_signature_parameters) - set(metadata_parameters)
        ):
            violations.append(
                f"{command_name}.{parameter_name}: accepted by execute but missing "
                "from metadata"
            )

        for parameter_name, metadata in metadata_parameters.items():
            signature_parameter = named_signature_parameters.get(parameter_name)
            if signature_parameter is None:
                continue
            signature_required = (
                signature_parameter.default is inspect.Parameter.empty
            )
            if bool(metadata.get("required", False)) != signature_required:
                violations.append(
                    f"{command_name}.{parameter_name}: required metadata disagrees "
                    "with execute"
                )
            if (
                "default" in metadata
                and not signature_required
                and signature_parameter.default is not None
                and metadata["default"] != signature_parameter.default
            ):
                violations.append(
                    f"{command_name}.{parameter_name}: public default "
                    f"{metadata['default']!r} disagrees with execute default "
                    f"{signature_parameter.default!r}"
                )
            if (
                "default" not in metadata
                and not signature_required
                and signature_parameter.default is not None
            ):
                violations.append(
                    f"{command_name}.{parameter_name}: execute default "
                    f"{signature_parameter.default!r} is undocumented"
                )

        for safety_attribute in (
            "approval_when_parameter",
            "backup_target_parameter",
        ):
            target_parameter = getattr(command_class, safety_attribute, None)
            if target_parameter and target_parameter not in seen_names:
                violations.append(
                    f"{command_name}: {safety_attribute} refers to missing "
                    f"parameter {target_parameter!r}"
                )

        examples = command_class.examples
        if not isinstance(examples, list) or not examples:
            violations.append(f"{command_name}: at least one example is required")
            continue
        canonical_prefix = f"qzx {command_name}"
        if not any(
            isinstance(example, dict)
            and isinstance(example.get("command"), str)
            and (
                example["command"] == canonical_prefix
                or example["command"].startswith(canonical_prefix + " ")
            )
            for example in examples
        ):
            violations.append(
                f"{command_name}: examples need one canonical invocation beginning "
                f"with {canonical_prefix!r}"
            )

    return loader, violations


def test_command_catalog_metadata_matches_public_execute_signatures():
    loader, violations = _catalog_contract_violations()

    assert loader.load_errors == {}
    assert loader.registration_warnings == []
    assert violations == [], (
        "Command metadata is executable API, not descriptive decoration:\n"
        + "\n".join(violations)
    )

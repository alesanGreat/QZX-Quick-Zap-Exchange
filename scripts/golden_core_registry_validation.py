"""Semantic validators for the QZX Golden Core candidate registry."""

from __future__ import annotations

import re
from collections import Counter

from qzx.core.command_loader import CommandLoader


_ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_REQUIRED_DIMENSIONS = {
    "behavioral_tests",
    "policy_review",
    "success_evidence",
    "failure_evidence",
    "result_contract_review",
    "platform_evidence",
    "release_quality",
    "lifecycle_review",
}


def validate_registry_metadata(registry):
    errors = []
    if registry.get("schema_version") != 1:
        errors.append("golden-core.json must use schema_version 1.")
    if registry.get("name") != "QZX Golden Core":
        errors.append("golden-core.json must identify QZX Golden Core.")
    if registry.get("status") != "candidate":
        errors.append(
            "Golden Core must remain a candidate until separately reviewed."
        )
    if registry.get("target_maturity") != "beta":
        errors.append("Golden Core target_maturity must be beta.")
    for field in (
        "selected_on",
        "maintainer",
        "purpose",
        "purpose_es",
        "disclaimer",
        "disclaimer_es",
    ):
        if not nonempty_text(registry.get(field)):
            errors.append(
                f"Golden Core {field} must be non-empty text."
            )
    errors.extend(_selection_principle_errors(registry))
    return errors


def _selection_principle_errors(registry):
    principles = registry.get("selection_principles")
    if not isinstance(principles, list) or len(principles) < 4:
        return [
            "Golden Core must declare at least four selection principles."
        ]
    errors = []
    for index, principle in enumerate(principles):
        if not isinstance(principle, dict) or any(
            not nonempty_text(principle.get(locale))
            for locale in ("en", "es")
        ):
            errors.append(
                f"selection_principles[{index}] must contain English "
                "and Spanish text."
            )
    return errors


def validate_readiness_dimensions(registry):
    dimensions = registry.get("readiness_dimensions")
    if not isinstance(dimensions, list):
        return ["Golden Core readiness_dimensions must be an array."]
    errors = []
    dimension_ids = []
    for index, item in enumerate(dimensions):
        item_errors, dimension_id = _dimension_errors(index, item)
        errors.extend(item_errors)
        if dimension_id is not None:
            dimension_ids.append(dimension_id)
    errors.extend(_dimension_set_errors(dimension_ids))
    return errors


def _dimension_errors(index, item):
    context = f"readiness_dimensions[{index}]"
    if not isinstance(item, dict):
        return [f"{context} must be an object."], None
    errors = []
    dimension_id = item.get("id")
    if (
        not isinstance(dimension_id, str)
        or _ROLE_PATTERN.fullmatch(dimension_id) is None
    ):
        errors.append(f"{context}.id must use lower_snake_case.")
        dimension_id = None
    if not nonempty_text(item.get("description")):
        errors.append(
            f"{context}.description must be non-empty text."
        )
    if not nonempty_text(item.get("description_es")):
        errors.append(
            f"{context}.description_es must be non-empty text."
        )
    return errors, dimension_id


def _dimension_set_errors(dimension_ids):
    errors = []
    duplicates = sorted(
        item
        for item, count in Counter(dimension_ids).items()
        if count > 1
    )
    if duplicates:
        errors.append(
            "Golden Core readiness dimensions are duplicated: "
            + ", ".join(duplicates)
            + "."
        )
    missing = sorted(_REQUIRED_DIMENSIONS - set(dimension_ids))
    extra = sorted(set(dimension_ids) - _REQUIRED_DIMENSIONS)
    if missing:
        errors.append(
            "Golden Core is missing readiness dimensions: "
            + ", ".join(missing)
            + "."
        )
    if extra:
        errors.append(
            "Golden Core has unknown readiness dimensions: "
            + ", ".join(extra)
            + "."
        )
    return errors


def command_registry_context(command_index, lifecycle):
    errors = []
    indexed = command_index.get("commands")
    indexed_names = {
        item.get("name")
        for item in indexed
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    } if isinstance(indexed, list) else set()
    if not indexed_names:
        errors.append("The packaged command index has no commands.")

    lifecycle_commands = lifecycle.get("commands")
    lifecycle_stages = lifecycle.get("stages")
    if (
        not isinstance(lifecycle_commands, dict)
        or not isinstance(lifecycle_stages, dict)
    ):
        errors.append(
            "The packaged command lifecycle registry is incomplete."
        )
        lifecycle_commands = {}
        lifecycle_stages = {}
    return indexed_names, lifecycle_commands, lifecycle_stages, errors


def validate_commands(
    registry,
    indexed_names,
    lifecycle_commands,
    lifecycle_stages,
):
    errors = []
    commands = registry.get("commands")
    if not isinstance(commands, list) or not 10 <= len(commands) <= 20:
        errors.append(
            "Golden Core must contain between 10 and 20 commands."
        )
        commands = []

    command_names = []
    loader = CommandLoader()
    for index, item in enumerate(commands):
        name, item_errors = _command_errors(
            index,
            item,
            indexed_names,
            lifecycle_commands,
            lifecycle_stages,
            loader,
        )
        errors.extend(item_errors)
        if name is not None:
            command_names.append(name)
    errors.extend(_duplicate_command_errors(command_names))
    return command_names, errors


def _command_errors(
    index,
    item,
    indexed_names,
    lifecycle_commands,
    lifecycle_stages,
    loader,
):
    context = f"commands[{index}]"
    if not isinstance(item, dict):
        return None, [f"{context} must be an object."]

    name = item.get("name")
    if not nonempty_text(name):
        return None, [f"{context}.name must be non-empty text."]

    errors = _command_metadata_errors(context, item)
    if name not in indexed_names:
        errors.append(
            "Golden Core command is absent from command-index.json: "
            f"{name}."
        )
        return name, errors
    errors.extend(
        _command_runtime_errors(
            name,
            lifecycle_commands,
            lifecycle_stages,
            loader,
        )
    )
    return name, errors


def _command_metadata_errors(context, item):
    errors = []
    role = item.get("role")
    if not isinstance(role, str) or _ROLE_PATTERN.fullmatch(role) is None:
        errors.append(f"{context}.role must use lower_snake_case.")
    rationale = item.get("rationale")
    rationale_es = item.get("rationale_es")
    if not nonempty_text(rationale) or len(rationale.strip()) < 30:
        errors.append(f"{context}.rationale must explain the selection.")
    if not nonempty_text(rationale_es) or len(rationale_es.strip()) < 30:
        errors.append(
            f"{context}.rationale_es must explain the selection."
        )
    return errors


def _command_runtime_errors(
    name,
    lifecycle_commands,
    lifecycle_stages,
    loader,
):
    errors = []
    lifecycle_entry = lifecycle_commands.get(name)
    if not isinstance(lifecycle_entry, dict):
        errors.append(
            f"Golden Core command has no lifecycle entry: {name}."
        )
    else:
        stage = lifecycle_stages.get(lifecycle_entry.get("stage"))
        if (
            not isinstance(stage, dict)
            or stage.get("public_executable") is not True
        ):
            errors.append(
                f"Golden Core command is not publicly executable: {name}."
            )

    command = loader.get_command(name)
    if command is None:
        errors.append(f"Golden Core command could not be loaded: {name}.")
        return errors
    if command.name != name:
        errors.append(
            f"Golden Core command does not use its canonical name: {name}."
        )
    if bool(getattr(command, "requires_explicit_approval", False)):
        errors.append(
            f"Golden Core command requires high-risk approval: {name}."
        )
    if getattr(command, "backup_target_parameter", None) is not None:
        errors.append(
            f"Golden Core command declares a mutation backup target: {name}."
        )
    return errors


def _duplicate_command_errors(command_names):
    duplicates = sorted(
        name
        for name, count in Counter(command_names).items()
        if count > 1
    )
    if not duplicates:
        return []
    return [
        "Golden Core commands are duplicated: "
        + ", ".join(duplicates)
        + "."
    ]


def validate_failure_policy(registry, command_names):
    policy = registry.get("failure_evidence_policy")
    if not isinstance(policy, dict):
        return ["Golden Core must declare failure_evidence_policy."]

    errors = []
    required = policy.get("required_commands")
    not_applicable = policy.get("not_applicable")
    if not isinstance(required, list) or any(
        not nonempty_text(name) for name in required
    ):
        errors.append(
            "failure_evidence_policy.required_commands must be a text array."
        )
        required = []
    if not isinstance(not_applicable, dict):
        errors.append(
            "failure_evidence_policy.not_applicable must be an object."
        )
        not_applicable = {}
    else:
        errors.extend(_not_applicable_errors(not_applicable))
    errors.extend(
        _failure_policy_set_errors(required, not_applicable, command_names)
    )
    return errors


def _not_applicable_errors(not_applicable):
    errors = []
    for name, explanation in not_applicable.items():
        if not nonempty_text(name) or not isinstance(explanation, dict):
            errors.append(
                "Every failure-evidence not_applicable entry must be an object."
            )
            continue
        if not nonempty_text(explanation.get("reason")):
            errors.append(
                f"Failure evidence N/A reason is missing for {name}."
            )
        if not nonempty_text(explanation.get("reason_es")):
            errors.append(
                f"Failure evidence Spanish N/A reason is missing for {name}."
            )
    return errors


def _failure_policy_set_errors(required, not_applicable, command_names):
    errors = []
    required_set = set(required)
    not_applicable_set = set(not_applicable)
    command_set = set(command_names)
    duplicates = sorted(
        name for name, count in Counter(required).items() if count > 1
    )
    if duplicates:
        errors.append(
            "Failure-evidence required commands are duplicated: "
            + ", ".join(duplicates)
            + "."
        )
    overlap = sorted(required_set & not_applicable_set)
    unknown = sorted((required_set | not_applicable_set) - command_set)
    missing = sorted(command_set - (required_set | not_applicable_set))
    if overlap:
        errors.append(
            "Failure evidence cannot be both required and not applicable: "
            + ", ".join(overlap)
            + "."
        )
    if unknown:
        errors.append(
            "Failure-evidence policy contains unknown commands: "
            + ", ".join(unknown)
            + "."
        )
    if missing:
        errors.append(
            "Failure-evidence policy does not classify commands: "
            + ", ".join(missing)
            + "."
        )
    return errors


def validate_release_quality_policy(registry):
    policy = registry.get("release_quality_policy")
    if not isinstance(policy, dict):
        return ["Golden Core must declare release_quality_policy."]

    errors = []
    path = policy.get("attestation_path")
    if (
        not nonempty_text(path)
        or not str(path).startswith("docs/release-quality/")
        or not str(path).endswith(".json")
        or ".." in str(path).split("/")
    ):
        errors.append(
            "release_quality_policy.attestation_path must be a safe "
            "docs/release-quality JSON path."
        )
    if not nonempty_text(policy.get("blocking_issue_label")):
        errors.append(
            "release_quality_policy.blocking_issue_label must be non-empty text."
        )
    errors.extend(_required_release_quality_flags(policy))
    if not nonempty_text(policy.get("note")):
        errors.append(
            "release_quality_policy.note must be non-empty text."
        )
    if not nonempty_text(policy.get("note_es")):
        errors.append(
            "release_quality_policy.note_es must be non-empty text."
        )
    return errors


def _required_release_quality_flags(policy):
    errors = []
    for flag in (
        "requires_exact_release_tag",
        "requires_verified_distribution_hashes",
        "requires_successful_ci",
        "requires_digest_bound_platform_evidence",
        "requires_zero_known_release_blockers",
    ):
        if policy.get(flag) is not True:
            errors.append(
                f"release_quality_policy.{flag} must be true."
            )
    return errors


def validate_catalog(catalog, command_names):
    commands = catalog.get("commands")
    if not isinstance(commands, dict):
        return ["The generated command catalog has no commands object."]
    errors = []
    for name in command_names:
        errors.extend(_catalog_command_errors(commands, name))
    return errors


def _catalog_command_errors(commands, name):
    command = commands.get(name)
    if not isinstance(command, dict):
        return [
            f"Generated catalog is missing Golden Core command: {name}."
        ]
    errors = []
    safety = command.get("safety")
    availability = command.get("availability")
    if not isinstance(safety, dict) or safety.get("operation") != "read-only":
        errors.append(
            "Reviewed policy is not read-only for Golden Core command: "
            f"{name}."
        )
    if isinstance(safety, dict) and safety.get("privilege_sensitive") is not False:
        errors.append(f"Golden Core command is privilege-sensitive: {name}.")
    if isinstance(safety, dict) and safety.get("shares_external_data") is not False:
        errors.append(f"Golden Core command shares external data: {name}.")
    if (
        not isinstance(availability, dict)
        or not isinstance(availability.get("included_in_pypi"), bool)
    ):
        errors.append(
            "Golden Core command has invalid package-availability metadata: "
            f"{name}."
        )
    return errors


def nonempty_text(value):
    return isinstance(value, str) and value.strip() != ""

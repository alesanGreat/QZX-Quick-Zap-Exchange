"""Orchestration for read-only project bootstrap planning."""

from pathlib import Path


def _target(command, path):
    try:
        target = Path(path).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return None, command._failure(
            "invalid_target", f"{type(exc).__name__}: {exc}",
            "Choose a valid project directory path.", path,
        )
    if target.exists() and not target.is_dir():
        return None, command._failure(
            "target_not_directory", f"Bootstrap target '{target}' is not a directory.",
            "Choose a project directory or a path that does not exist yet.", target,
        )
    entries, error = command._root_entries(target)
    if error:
        return None, command._failure(
            "target_not_readable", error, "Check directory permissions and retry.", target
        )
    return (target, entries), None


def _selection(command, target, entries, tech, components):
    technology, detection = command._select_technology(tech, entries)
    if technology is None:
        error_code, error, message = detection
        return None, command._failure(
            error_code, error, message, target,
            detected_candidates=command._detect_technologies(entries),
            supported_technologies=list(command.SUPPORTED_TECHNOLOGIES),
        )
    selected, error = command._select_components(components)
    if error:
        return None, command._failure(
            "invalid_components", error,
            "Choose a comma-separated subset or use 'all'. No files or commands were changed.",
            target, supported_components=list(command.COMPONENTS),
        )
    return (technology, detection, selected), None


def _summary(steps):
    return {
        "total_steps": len(steps),
        "would_create": sum(item["status"] == "would_create" for item in steps),
        "manual_review": sum(item["status"] == "manual_review" for item in steps),
        "network_steps": sum(item["network"] for item in steps),
        "sensitive_steps": sum(item["sensitive"] for item in steps),
        "filesystem_mutating_steps": sum(item["mutates_files"] for item in steps),
        "externally_mutating_steps": sum(item["mutates_external_state"] for item in steps),
        "executed_steps": 0,
    }


def _message(technology, target, components, steps, summary):
    return (
        "Prepared a read-only {} bootstrap plan for '{}' with {} selected "
        "components and {} steps. QZX executed no steps. Proposed effects: {} "
        "filesystem creations; {} manual-review steps; {} network-capable; {} "
        "sensitive; {} filesystem-mutating; {} external-state-mutating."
    ).format(
        technology, target, len(components), len(steps), summary["would_create"],
        summary["manual_review"], summary["network_steps"],
        summary["sensitive_steps"], summary["filesystem_mutating_steps"],
        summary["externally_mutating_steps"],
    )


def execute_bootstrap_plan(command, path=".", tech=None, components="all"):
    target_data, failure = _target(command, path)
    if failure:
        return failure
    target, entries = target_data
    selection, failure = _selection(command, target, entries, tech, components)
    if failure:
        return failure
    technology, detection, selected = selection
    steps = []
    for component in selected:
        steps.extend(command._component_steps(component, technology, target, entries))
    summary = _summary(steps)
    return {
        "success": True,
        "message": _message(technology, target, selected, steps, summary),
        "details": {
            "path": str(target), "path_exists": target.exists(),
            "technology": technology, "technology_selection": detection,
            "selected_components": selected, "steps": steps, "summary": summary,
            "execution": {
                "read_only": True, "files_written": 0, "commands_run": 0,
                "network_requests": 0, "secrets_generated": 0,
            },
            "recommended_scaffold_command": command.SCAFFOLD_COMMANDS[technology],
        },
    }

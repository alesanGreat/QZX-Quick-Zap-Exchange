"""Small shared helpers for language-specific scaffold commands."""

import datetime
import os


def parse_scaffold_boolean(value, name):
    """Parse a scaffold boolean strictly for direct and CLI execution alike."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "on"}:
            return True
        if normalized in {"false", "no", "n", "0", "off"}:
            return False
    raise ValueError(f"{name} must be true or false, got {value!r}.")


def normalize_project_name(
    name,
    *,
    separator="_",
    replacement_characters=(" ", "-"),
    leading_prefix=None,
    lowercase=True,
):
    """Normalize a project name while preserving each ecosystem's conventions."""
    normalized = name
    for character in replacement_characters:
        normalized = normalized.replace(character, separator)

    normalized = "".join(
        character
        for character in normalized
        if character.isalnum() or character == separator
    )
    if (
        leading_prefix
        and normalized
        and not (normalized[0].isalpha() or normalized[0] == separator)
    ):
        normalized = leading_prefix + normalized
    return normalized.lower() if lowercase else normalized


def prepare_scaffold_project(project_name, path, result_fields):
    """Validate and create the common project root and initial result."""
    if not project_name:
        return {
            "success": False,
            "error": "Invalid project name",
            "message": (
                "Project name cannot be empty and must contain valid "
                "characters (letters, numbers, underscores)."
            ),
        }

    if not os.path.exists(path):
        return {
            "success": False,
            "error": f"Path does not exist: {path}",
            "message": (
                f"Cannot create project: the specified path '{path}' does not exist."
            ),
        }

    project_path = os.path.join(path, project_name)
    if os.path.exists(project_path):
        return {
            "success": False,
            "error": f"Project directory already exists: {project_path}",
            "message": (
                f"Cannot create project: directory '{project_path}' already exists."
            ),
        }

    result = {
        "success": True,
        "project_name": project_name,
        "project_path": project_path,
    }
    result.update(result_fields)
    result["files_created"] = []
    result["timestamp"] = datetime.datetime.now().isoformat()

    os.makedirs(project_path)
    result["files_created"].append(project_path)
    return result

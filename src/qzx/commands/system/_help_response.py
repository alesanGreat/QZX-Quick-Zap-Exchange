"""Help response assembly for the public help command."""

from __future__ import annotations


GENERAL_HELP = """QZX Help:

Usage: qzx <command> [arguments] [--json]

Output:
- Without --json: a clear terminal presentation with the summary and useful data.
- With --json: one complete structured object on stdout.
- Every public result contains boolean success and descriptive message fields.

Discovery:
- List the commands in this installation: qzx listCommands --json
- Inspect one command: qzx <command> --help
- Get structured command help: qzx <command> --help --json
- Identify this installation: qzx version --json

Naming:
- Command lookup is case-insensitive.
- Documentation uses each command's canonical lowerCamelCase spelling.
"""


def _known_command(loader, command, command_object):
    requested = str(command)
    return {
        "success": True,
        "command": requested,
        "message": command_object.get_help(),
        "details": {
            "name": command_object.name,
            "requested_name": requested,
            "canonical_name": command_object.name,
            "description": command_object.description,
            "category": command_object.category,
            "maturity": loader.get_command_maturity(command),
            "parameters": command_object.parameters,
            "examples": command_object.examples,
        },
    }


def _missing_command(loader, command):
    requested = str(command)
    suggestions = loader.suggest_command_names(requested)
    suggestion_text = (
        " Did you mean: {}?".format(", ".join(suggestions))
        if suggestions
        else ""
    )
    return {
        "success": False,
        "error": f"Command not found: {requested}",
        "error_code": "command_not_found",
        "message": (
            f"Command '{requested}' was not found."
            f"{suggestion_text} Use 'qzx listCommands' to see available commands."
        ),
        "details": {
            "requested": requested,
            "suggestions": suggestions,
        },
    }


def execute_help(loader, command=None):
    """Return general help or detailed help for one command."""
    if not command:
        return {"success": True, "message": GENERAL_HELP}
    command_object = loader.get_command(command)
    if command_object:
        return _known_command(loader, command, command_object)
    return _missing_command(loader, command)

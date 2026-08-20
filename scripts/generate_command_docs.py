#!/usr/bin/env python3
"""Generate QZX's deterministic public command reference from package metadata."""

from __future__ import annotations

import argparse
import inspect
import os
import sys
import tempfile
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
OUTPUT_PATH = REPOSITORY_ROOT / "docs" / "reference" / "commands-generated.md"

sys.path.insert(0, str(SOURCE_ROOT))

from qzx.core.command_lifecycle import command_maturity  # noqa: E402
from qzx.core.command_loader import CommandLoader  # noqa: E402


def discover_command_classes() -> list[type]:
    """Return every canonical command class or fail on partial discovery."""

    loader = CommandLoader()
    discovered = loader.discover_commands()
    if loader.load_errors:
        raise RuntimeError(f"Command discovery errors: {loader.load_errors}")
    if loader.registration_warnings:
        raise RuntimeError(
            "Command registration warnings: "
            f"{loader.registration_warnings}"
        )

    command_classes = set(discovered.values())
    if len(command_classes) != len(discovered):
        raise RuntimeError(
            "Command discovery returned aliases or duplicate class mappings; "
            "the public reference only accepts canonical commands."
        )
    return sorted(
        command_classes,
        key=lambda command: (command.category.casefold(), command.name.casefold()),
    )


def format_parameters(parameters: Iterable[dict[str, object]]) -> str:
    """Render command parameters as stable Markdown."""

    parameters = list(parameters)
    if not parameters:
        return "None"

    rendered: list[str] = []
    for parameter in parameters:
        name = parameter.get("name", "unnamed")
        description = parameter.get("description", "No description")
        required = bool(parameter.get("required", False))
        default = parameter.get("default")
        requirement = "Required" if required else "Optional"
        if isinstance(default, bool):
            default_value = str(default).lower()
        else:
            default_value = str(default)
        default_text = (
            f" (default: `{default_value}`)" if default is not None else ""
        )
        rendered.append(
            f"- `{name}`: {description} - {requirement}{default_text}"
        )
    return "\n".join(rendered)


def format_examples(examples: Iterable[dict[str, object]]) -> str:
    """Render command examples as stable Markdown."""

    examples = list(examples)
    if not examples:
        return "None"
    return "\n".join(
        "- `{}`\n  {}".format(
            example.get("command", ""),
            example.get("description", "No description"),
        )
        for example in examples
    )


def generate_command_document(command_class: type) -> str:
    """Render one command class without executing the command."""

    document = [f"### {command_class.name}"]
    class_documentation = inspect.getdoc(command_class)
    if class_documentation:
        document.append(f"\n{class_documentation}\n")

    maturity = command_maturity(command_class.name)
    document.extend(
        (
            f"**Category:** {command_class.category}",
            "**Maturity:** {} — {}".format(
                maturity["label"],
                maturity["summary"],
            ),
            f"**Description:** {command_class.description}",
            "\n**Parameters:**",
            format_parameters(command_class.parameters),
        )
    )

    if command_class.examples:
        document.extend(
            ("\n**Examples:**", format_examples(command_class.examples))
        )

    execute_documentation = inspect.getdoc(command_class.execute)
    if execute_documentation:
        document.extend(("\n**Details:**", execute_documentation))
    return "\n".join(document)


def group_by_category(command_classes: Iterable[type]) -> dict[str, list[type]]:
    """Group command classes while preserving deterministic ordering."""

    grouped: dict[str, list[type]] = defaultdict(list)
    for command_class in command_classes:
        grouped[command_class.category].append(command_class)
    return {
        category: sorted(commands, key=lambda command: command.name.casefold())
        for category, commands in sorted(
            grouped.items(), key=lambda item: item[0].casefold()
        )
    }


def generate_table_of_contents(categories: dict[str, list[type]]) -> str:
    """Render the deterministic Markdown table of contents."""

    lines = ["## Table of Contents\n"]
    for category, command_classes in categories.items():
        category_display = category.capitalize()
        lines.append(f"- [{category_display} Commands](#{category}-commands)")
        lines.extend(
            f"  - [{command.name}](#{command.name.casefold()})"
            for command in command_classes
        )
    return "\n".join(lines)


def generate_reference(command_classes: Iterable[type] | None = None) -> str:
    """Return the complete byte-stable Markdown projection."""

    if command_classes is None:
        command_classes = discover_command_classes()
    categories = group_by_category(command_classes)

    lines = [
        "# QZX Commands Documentation",
        "",
        "> Generated deterministically by `python -B scripts/generate_command_docs.py`.",
        "> Do not edit by hand; update command metadata or lifecycle sources, then regenerate.",
        "",
        generate_table_of_contents(categories),
        (
            "\n## Command maturity\n\n"
            "Every executable command has a fail-closed lifecycle assessment. "
            "Planning and proof-of-concept work stays outside the public loader; "
            "Alpha, Beta, Release Candidate, Stable, Deprecated, and Retired "
            "describe the command contract independently from the QZX package "
            "release channel. Immutable release tags preserve each version's "
            "assessment."
        ),
    ]

    for category, category_commands in categories.items():
        lines.append(f"\n## {category.capitalize()} Commands\n")
        for command_class in category_commands:
            lines.append(generate_command_document(command_class))
            lines.append("\n---\n")

    markdown = "\n".join(lines)
    return "\n".join(line.rstrip() for line in markdown.splitlines()) + "\n"


def write_if_changed(path: Path, content: str) -> bool:
    """Atomically replace ``path`` only when its UTF-8 bytes changed."""

    existing = path.read_text(encoding="utf-8") if path.is_file() else None
    if existing == content:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail without writing when the maintained reference is stale.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    try:
        generated = generate_reference()
        existing = (
            OUTPUT_PATH.read_text(encoding="utf-8")
            if OUTPUT_PATH.is_file()
            else None
        )
        if arguments.check:
            if existing != generated:
                print(
                    "Generated command reference is stale. Run "
                    "`python -B scripts/generate_command_docs.py`.",
                    file=sys.stderr,
                )
                return 1
            print("Generated command reference is up to date.")
            return 0

        changed = write_if_changed(OUTPUT_PATH, generated)
        print(
            "Updated generated command reference."
            if changed
            else "Generated command reference is already up to date."
        )
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Could not generate command reference: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

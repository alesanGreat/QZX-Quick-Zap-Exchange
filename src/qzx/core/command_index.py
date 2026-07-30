"""Validated packaged index for constant-I/O command lookup.

Normal CLI invocations read this single resource and import only the requested
command module.  Full module discovery remains the source used to regenerate
and verify the index in development and CI.
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re


COMMAND_INDEX_SCHEMA_VERSION = 2
COMMAND_INDEX_PATH = (
    Path(__file__).resolve().parents[1] / "resources" / "command-index.json"
)
_MODULE_PATTERN = re.compile(r"^qzx\.commands(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
_CLASS_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class CommandIndexError(RuntimeError):
    """The packaged command index is absent, malformed, or stale."""


@lru_cache(maxsize=1)
def load_command_index():
    """Load and validate the packaged index exactly once per process."""
    try:
        with COMMAND_INDEX_PATH.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CommandIndexError(
            "Unable to load command index '{}': {}: {}.".format(
                COMMAND_INDEX_PATH,
                type(exc).__name__,
                exc,
            )
        ) from exc
    return validate_command_index_document(document)


def validate_command_index_document(document):
    """Validate index structure, types, ordering, and canonical-name uniqueness."""
    if not isinstance(document, dict):
        raise CommandIndexError("Command index must contain one JSON object.")
    if document.get("schema_version") != COMMAND_INDEX_SCHEMA_VERSION:
        raise CommandIndexError(
            "Unsupported command index schema: {!r}.".format(
                document.get("schema_version")
            )
        )
    commands = document.get("commands")
    if not isinstance(commands, list) or not commands:
        raise CommandIndexError(
            "Command index must contain a non-empty commands list."
        )

    expected_fields = {
        "name",
        "module",
        "class_name",
        "description",
        "category",
    }
    canonical_names = set()
    canonical_order = []
    for index, entry in enumerate(commands):
        if not isinstance(entry, dict) or set(entry) != expected_fields:
            raise CommandIndexError(
                "Command index entry {} must contain exactly: {}.".format(
                    index,
                    ", ".join(sorted(expected_fields)),
                )
            )
        for field in ("name", "module", "class_name", "description", "category"):
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise CommandIndexError(
                    "Command index entry {} field '{}' must be non-empty text.".format(
                        index,
                        field,
                    )
                )
        if not _MODULE_PATTERN.fullmatch(entry["module"]):
            raise CommandIndexError(
                "Command '{}' has invalid module '{}' in the index.".format(
                    entry["name"],
                    entry["module"],
                )
            )
        if not _CLASS_PATTERN.fullmatch(entry["class_name"]):
            raise CommandIndexError(
                "Command '{}' has invalid class name '{}' in the index.".format(
                    entry["name"],
                    entry["class_name"],
                )
            )
        canonical = entry["name"].lower()
        if canonical in canonical_names:
            raise CommandIndexError(
                "Command index contains duplicate canonical command '{}'.".format(
                    entry["name"]
                )
            )
        canonical_names.add(canonical)
        canonical_order.append((canonical, entry["name"]))
    if canonical_order != sorted(canonical_order):
        raise CommandIndexError(
            "Command index entries must be sorted by canonical command name."
        )
    return document


@lru_cache(maxsize=1)
def command_index_lookup():
    """Map every case-insensitive canonical name to one metadata record."""
    return {
        entry["name"].lower(): entry
        for entry in load_command_index()["commands"]
    }


def indexed_command(command_name):
    """Return indexed metadata for a canonical command name."""
    if not isinstance(command_name, str):
        return None
    return command_index_lookup().get(command_name.lower())


def indexed_command_names():
    """Return every canonical command name with its published casing."""
    return tuple(
        entry["name"]
        for entry in indexed_command_records()
    )


def indexed_command_records():
    """Return canonical metadata records in deterministic order."""
    return tuple(load_command_index()["commands"])


def build_command_index(command_classes):
    """Build canonical metadata from fully discovered command classes."""
    entries = []
    for command_class in sorted(
        set(command_classes),
        key=lambda item: (item.name.lower(), item.name),
    ):
        instance = command_class()
        entries.append(
            {
                "name": instance.name,
                "module": command_class.__module__,
                "class_name": command_class.__name__,
                "description": instance.description,
                "category": instance.category,
            }
        )
    return validate_command_index_document(
        {
            "schema_version": COMMAND_INDEX_SCHEMA_VERSION,
            "commands": entries,
        }
    )


def validate_command_index_inventory(command_classes):
    """Require the packaged index to exactly match full runtime discovery."""
    expected = build_command_index(command_classes)
    actual = load_command_index()
    if actual != expected:
        raise CommandIndexError(
            "Packaged command index is stale. Run "
            "'python scripts/sync_command_index.py --write' and review the diff."
        )
    return actual


def validate_loaded_command(entry, command_class):
    """Require a lazily imported class to match every indexed public field."""
    actual = build_command_index([command_class])["commands"][0]
    if actual != entry:
        raise CommandIndexError(
            "Command index entry for '{}' does not match loaded class '{}.{}'. "
            "Regenerate the command index before running QZX.".format(
                entry["name"],
                command_class.__module__,
                command_class.__name__,
            )
        )
    return command_class


def write_command_index(document, destination=COMMAND_INDEX_PATH):
    """Atomically write a generated command index."""
    import os
    import tempfile

    validate_command_index_document(document)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".command-index-",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, destination)
        temporary_name = None
    finally:
        if temporary_name and os.path.lexists(temporary_name):
            os.unlink(temporary_name)

    load_command_index.cache_clear()
    command_index_lookup.cache_clear()
    return destination

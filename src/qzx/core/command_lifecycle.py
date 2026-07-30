#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Canonical command lifecycle metadata and fail-closed validation."""

from datetime import date
from functools import lru_cache
import json
from pathlib import Path, PurePosixPath
import re


LIFECYCLE_MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "resources"
    / "command-lifecycle.json"
)
EXPECTED_STAGES = {
    "planning",
    "proof_of_concept",
    "alpha",
    "beta",
    "release_candidate",
    "stable",
    "deprecated",
    "retired",
}
ROADMAP_STAGES = {"planning", "proof_of_concept"}
REVIEW_REQUIRED_STAGES = {
    "beta",
    "release_candidate",
    "stable",
    "deprecated",
}


class CommandLifecycleError(RuntimeError):
    """Raised when command maturity metadata is missing or inconsistent."""


def _require_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise CommandLifecycleError(
            "Command lifecycle field '{}' must be non-empty text.".format(field)
        )
    return value.strip()


def _validate_stage_definitions(document):
    stages = document.get("stages")
    if not isinstance(stages, dict) or set(stages) != EXPECTED_STAGES:
        missing = sorted(EXPECTED_STAGES - set(stages or {}))
        unexpected = sorted(set(stages or {}) - EXPECTED_STAGES)
        raise CommandLifecycleError(
            "Command lifecycle stages are incomplete. Missing: {}; unexpected: {}.".format(
                ", ".join(missing) or "none",
                ", ".join(unexpected) or "none",
            )
        )

    sequences = set()
    for stage_name, stage in stages.items():
        if not isinstance(stage, dict):
            raise CommandLifecycleError(
                "Command lifecycle stage '{}' must be an object.".format(stage_name)
            )
        _require_text(stage.get("label"), "{}.label".format(stage_name))
        _require_text(stage.get("summary"), "{}.summary".format(stage_name))
        _require_text(
            stage.get("stability"),
            "{}.stability".format(stage_name),
        )
        sequence = stage.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            raise CommandLifecycleError(
                "Command lifecycle stage '{}.sequence' must be an integer.".format(
                    stage_name
                )
            )
        if sequence in sequences:
            raise CommandLifecycleError(
                "Command lifecycle sequence {} is duplicated.".format(sequence)
            )
        sequences.add(sequence)
        if not isinstance(stage.get("public_executable"), bool):
            raise CommandLifecycleError(
                "Command lifecycle stage '{}.public_executable' must be boolean.".format(
                    stage_name
                )
            )
        if not isinstance(stage.get("promotion_review_required"), bool):
            raise CommandLifecycleError(
                "Command lifecycle stage "
                "'{}.promotion_review_required' must be boolean.".format(
                    stage_name
                )
            )
        requirements = stage.get("promotion_requirements")
        if not isinstance(requirements, list) or not requirements:
            raise CommandLifecycleError(
                "Command lifecycle stage "
                "'{}.promotion_requirements' must be a non-empty list.".format(
                    stage_name
                )
            )
        for index, requirement in enumerate(requirements):
            _require_text(
                requirement,
                "{}.promotion_requirements[{}]".format(stage_name, index),
            )

    configured_review_stages = {
        stage_name
        for stage_name, stage in stages.items()
        if stage["promotion_review_required"]
    }
    if configured_review_stages != REVIEW_REQUIRED_STAGES:
        raise CommandLifecycleError(
            "Lifecycle promotion review gates differ from policy. "
            "Expected: {}; configured: {}.".format(
                ", ".join(sorted(REVIEW_REQUIRED_STAGES)),
                ", ".join(sorted(configured_review_stages)),
            )
        )

    for stage_name in ROADMAP_STAGES | {"retired"}:
        if stages[stage_name]["public_executable"]:
            raise CommandLifecycleError(
                "Lifecycle stage '{}' cannot be publicly executable.".format(
                    stage_name
                )
            )
    for stage_name in EXPECTED_STAGES - ROADMAP_STAGES - {"retired"}:
        if not stages[stage_name]["public_executable"]:
            raise CommandLifecycleError(
                "Lifecycle stage '{}' must remain publicly executable.".format(
                    stage_name
                )
            )


def _validate_review_reference(value, field):
    reference = _require_text(value, field).replace("\\", "/")
    path = PurePosixPath(reference)
    if (
        not path.parts
        or path.is_absolute()
        or ".." in path.parts
        or ":" in path.parts[0]
    ):
        raise CommandLifecycleError(
            "Command lifecycle evidence reference '{}' must be repository-relative.".format(
                value
            )
        )
    return reference


def _validate_promotion_review(command_name, review, replacement_required, commands):
    if not isinstance(review, dict):
        raise CommandLifecycleError(
            "Lifecycle review for '{}' must be an object.".format(command_name)
        )
    required_fields = {"reviewed_on", "rationale", "evidence"}
    if replacement_required:
        required_fields.add("replacement")
    if set(review) != required_fields:
        raise CommandLifecycleError(
            "Lifecycle review for '{}' must contain exactly: {}.".format(
                command_name,
                ", ".join(sorted(required_fields)),
            )
        )

    reviewed_on = _require_text(
        review.get("reviewed_on"),
        "commands.{}.review.reviewed_on".format(command_name),
    )
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", reviewed_on) is None:
            raise ValueError
        date.fromisoformat(reviewed_on)
    except ValueError as exc:
        raise CommandLifecycleError(
            "Lifecycle review date for '{}' must use YYYY-MM-DD.".format(
                command_name
            )
        ) from exc
    _require_text(
        review.get("rationale"),
        "commands.{}.review.rationale".format(command_name),
    )
    evidence = review.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise CommandLifecycleError(
            "Lifecycle review evidence for '{}' must be a non-empty list.".format(
                command_name
            )
        )
    for index, reference in enumerate(evidence):
        _validate_review_reference(
            reference,
            "commands.{}.review.evidence[{}]".format(command_name, index),
        )

    if replacement_required:
        replacement = _require_text(
            review.get("replacement"),
            "commands.{}.review.replacement".format(command_name),
        )
        if replacement == command_name or replacement not in commands:
            raise CommandLifecycleError(
                "Deprecated command '{}' must identify another public command "
                "as its replacement.".format(command_name)
            )


def _validate_command_entries(document):
    stages = document["stages"]
    commands = document.get("commands")
    if not isinstance(commands, dict):
        raise CommandLifecycleError(
            "Command lifecycle 'commands' must be an object."
        )

    for command_name, entry in commands.items():
        _require_text(command_name, "commands key")
        if not isinstance(entry, dict):
            raise CommandLifecycleError(
                "Lifecycle entry for '{}' must be an object.".format(command_name)
            )
        if set(entry) - {"stage", "note", "review"}:
            raise CommandLifecycleError(
                "Lifecycle entry for '{}' contains unsupported fields: {}.".format(
                    command_name,
                    ", ".join(
                        sorted(set(entry) - {"stage", "note", "review"})
                    ),
                )
            )
        stage_name = _require_text(
            entry.get("stage"),
            "commands.{}.stage".format(command_name),
        )
        stage = stages.get(stage_name)
        if stage is None:
            raise CommandLifecycleError(
                "Command '{}' uses unknown lifecycle stage '{}'.".format(
                    command_name,
                    stage_name,
                )
            )
        if not stage["public_executable"]:
            raise CommandLifecycleError(
                "Public command '{}' cannot use non-executable stage '{}'.".format(
                    command_name,
                    stage_name,
                )
            )
        note = entry.get("note")
        if note is not None:
            _require_text(note, "commands.{}.note".format(command_name))
        review = entry.get("review")
        if stage["promotion_review_required"] and review is None:
            raise CommandLifecycleError(
                "Command '{}' cannot claim '{}' without a promotion review.".format(
                    command_name,
                    stage_name,
                )
            )
        if review is not None:
            _validate_promotion_review(
                command_name,
                review,
                replacement_required=stage_name == "deprecated",
                commands=commands,
            )


def _validate_roadmap_entries(document):
    roadmap = document.get("roadmap")
    if not isinstance(roadmap, dict):
        raise CommandLifecycleError(
            "Command lifecycle 'roadmap' must be an object."
        )

    public_names = {name.lower() for name in document["commands"]}
    proposed_names = set()
    for item_id, entry in roadmap.items():
        _require_text(item_id, "roadmap key")
        if not isinstance(entry, dict):
            raise CommandLifecycleError(
                "Roadmap entry '{}' must be an object.".format(item_id)
            )
        if set(entry) != {"proposed_name", "stage", "summary"}:
            raise CommandLifecycleError(
                "Roadmap entry '{}' must contain proposed_name, stage, and summary.".format(
                    item_id
                )
            )
        proposed_name = _require_text(
            entry.get("proposed_name"),
            "roadmap.{}.proposed_name".format(item_id),
        )
        stage_name = _require_text(
            entry.get("stage"),
            "roadmap.{}.stage".format(item_id),
        )
        _require_text(
            entry.get("summary"),
            "roadmap.{}.summary".format(item_id),
        )
        normalized_name = proposed_name.lower()
        if normalized_name in public_names:
            raise CommandLifecycleError(
                "Roadmap item '{}' duplicates public command '{}'.".format(
                    item_id,
                    proposed_name,
                )
            )
        if normalized_name in proposed_names:
            raise CommandLifecycleError(
                "Roadmap proposed command '{}' is duplicated.".format(proposed_name)
            )
        proposed_names.add(normalized_name)
        if stage_name not in ROADMAP_STAGES:
            raise CommandLifecycleError(
                "Roadmap item '{}' must be planning or proof_of_concept, not '{}'.".format(
                    item_id,
                    stage_name,
                )
            )


def validate_lifecycle_document(document):
    """Validate the lifecycle schema without comparing runtime discovery."""
    if not isinstance(document, dict):
        raise CommandLifecycleError(
            "Command lifecycle manifest must contain one JSON object."
        )
    if document.get("schema_version") != 2:
        raise CommandLifecycleError(
            "Unsupported command lifecycle schema version: {}.".format(
                document.get("schema_version")
            )
        )
    assessment = document.get("assessment")
    if not isinstance(assessment, dict):
        raise CommandLifecycleError(
            "Command lifecycle 'assessment' must be an object."
        )
    for field in (
        "scope",
        "baseline",
        "established_after_version",
        "history",
    ):
        _require_text(assessment.get(field), "assessment.{}".format(field))

    _validate_stage_definitions(document)
    _validate_command_entries(document)
    _validate_roadmap_entries(document)
    return document


@lru_cache(maxsize=1)
def load_command_lifecycle():
    """Load and validate the lifecycle manifest shipped with QZX."""
    try:
        with LIFECYCLE_MANIFEST_PATH.open("r", encoding="utf-8") as lifecycle_file:
            document = json.load(lifecycle_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise CommandLifecycleError(
            "Unable to load command lifecycle manifest '{}': {}.".format(
                LIFECYCLE_MANIFEST_PATH,
                exc,
            )
        ) from exc
    return validate_lifecycle_document(document)


def validate_lifecycle_inventory(canonical_command_names):
    """Require an exact lifecycle entry for every discovered public command."""
    document = load_command_lifecycle()
    discovered = set(canonical_command_names)
    declared = set(document["commands"])
    missing = sorted(discovered - declared)
    obsolete = sorted(declared - discovered)
    if missing or obsolete:
        raise CommandLifecycleError(
            "Command lifecycle inventory differs from runtime discovery. "
            "Missing: {}; obsolete: {}.".format(
                ", ".join(missing) or "none",
                ", ".join(obsolete) or "none",
            )
        )
    return document


def validate_lifecycle_evidence_files(document, repository_root):
    """Require every promotion review reference to resolve inside the repo."""
    validate_lifecycle_document(document)
    root = Path(repository_root).resolve()
    missing = []
    escaped = []
    for command_name, entry in document["commands"].items():
        review = entry.get("review")
        if review is None:
            continue
        for reference in review["evidence"]:
            candidate = (root / reference).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                escaped.append("{}: {}".format(command_name, reference))
                continue
            if not candidate.is_file():
                missing.append("{}: {}".format(command_name, reference))

    if escaped or missing:
        raise CommandLifecycleError(
            "Command lifecycle promotion evidence is unavailable. "
            "Escaped repository: {}; missing files: {}.".format(
                ", ".join(escaped) or "none",
                ", ".join(missing) or "none",
            )
        )
    return document


def stage_maturity(stage_name, assessment_scope):
    """Return normalized details for one validated executable stage."""
    document = load_command_lifecycle()
    stage = document["stages"].get(stage_name)
    if stage is None or not stage["public_executable"]:
        raise CommandLifecycleError(
            "Lifecycle stage '{}' is not valid for an executable command.".format(
                stage_name
            )
        )
    return {
        "stage": stage_name,
        "label": stage["label"],
        "sequence": stage["sequence"],
        "public_executable": stage["public_executable"],
        "stability": stage["stability"],
        "summary": stage["summary"],
        "promotion_review_required": stage["promotion_review_required"],
        "assessment_scope": assessment_scope,
    }


def command_maturity(command_name):
    """Return normalized maturity details for one canonical public command."""
    document = load_command_lifecycle()
    entry = document["commands"].get(command_name)
    if entry is None:
        raise CommandLifecycleError(
            "Public command '{}' has no lifecycle entry.".format(command_name)
        )
    result = stage_maturity(
        entry["stage"],
        document["assessment"]["scope"],
    )
    if entry.get("note"):
        result["note"] = entry["note"]
    if entry.get("review"):
        result["review"] = entry["review"]
    return result

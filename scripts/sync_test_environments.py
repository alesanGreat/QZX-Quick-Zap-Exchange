#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Synchronize public test-environment wording from its canonical JSON source."""

import argparse
import json
import re
from pathlib import Path
from string import Formatter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "src" / "qzx" / "resources" / "test-environments.json"
README_PATH = PROJECT_ROOT / "README.md"
START_MARKER = "<!-- BEGIN GENERATED TEST ENVIRONMENTS -->"
END_MARKER = "<!-- END GENERATED TEST ENVIRONMENTS -->"
PUBLISHED_LOCALES = ("en", "es")
PROHIBITED_RESULT_KEYS = {
    "conclusion",
    "failed",
    "passed",
    "result",
    "run_id",
    "run_url",
    "status",
    "tests_passed",
}


def load_manifest():
    with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _require_non_empty_string(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("{} must be a non-empty string.".format(label))


def _validate_result_neutral(value, path="root"):
    if isinstance(value, dict):
        prohibited = PROHIBITED_RESULT_KEYS.intersection(value)
        if prohibited:
            raise ValueError(
                "{} contains run-result fields: {}".format(
                    path,
                    ", ".join(sorted(prohibited)),
                )
            )
        for key, child in value.items():
            _validate_result_neutral(child, "{}.{}".format(path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_result_neutral(child, "{}[{}]".format(path, index))


def validate_manifest(manifest, validate_workflows=True):
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("test-environments.json must use schema_version 1.")
    _validate_result_neutral(manifest)

    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        raise ValueError("test-environments.json is missing runtime.")
    for key in ("implementation", "version", "build"):
        _require_non_empty_string(runtime.get(key), "runtime.{}".format(key))
    for locale in PUBLISHED_LOCALES:
        _require_non_empty_string(
            runtime.get("display", {}).get(locale),
            "runtime.display.{}".format(locale),
        )

    for collection_name in ("summary_templates", "scope_notes"):
        collection = manifest.get(collection_name)
        if not isinstance(collection, dict):
            raise ValueError("{} must be an object.".format(collection_name))
        for locale in PUBLISHED_LOCALES:
            _require_non_empty_string(
                collection.get(locale),
                "{}.{}".format(collection_name, locale),
            )
    expected_fields = {"platforms", "python"}
    for locale, template in manifest["summary_templates"].items():
        fields = {
            field_name
            for _, field_name, _, _ in Formatter().parse(template)
            if field_name
        }
        if fields != expected_fields:
            raise ValueError(
                "summary_templates.{} must use exactly {}.".format(
                    locale,
                    sorted(expected_fields),
                )
            )

    environments = manifest.get("environments")
    if not isinstance(environments, list) or not environments:
        raise ValueError("test-environments.json must list environments.")

    environment_ids = set()
    referenced_workflows = set()
    for index, environment in enumerate(environments):
        label = "environments[{}]".format(index)
        if not isinstance(environment, dict):
            raise ValueError("{} must be an object.".format(label))
        environment_id = environment.get("id")
        _require_non_empty_string(environment_id, "{}.id".format(label))
        if environment_id in environment_ids:
            raise ValueError("Duplicate test environment id: {}".format(environment_id))
        environment_ids.add(environment_id)
        for locale in PUBLISHED_LOCALES:
            _require_non_empty_string(
                environment.get("name", {}).get(locale),
                "{}.name.{}".format(label, locale),
            )
        for key in ("version", "architecture"):
            _require_non_empty_string(
                environment.get(key),
                "{}.{}".format(label, key),
            )

        references = environment.get("workflow_references")
        if not isinstance(references, list) or not references:
            raise ValueError("{} must reference a workflow.".format(label))
        for reference in references:
            if not isinstance(reference, dict):
                raise ValueError("{} has an invalid workflow reference.".format(label))
            relative_path = reference.get("path")
            target = reference.get("target")
            _require_non_empty_string(relative_path, "{} workflow path".format(label))
            _require_non_empty_string(target, "{} workflow target".format(label))
            if not relative_path.startswith(".github/workflows/"):
                raise ValueError(
                    "{} references a workflow outside .github/workflows.".format(label)
                )
            referenced_workflows.add(relative_path)
            if validate_workflows:
                workflow_path = PROJECT_ROOT / relative_path
                if not workflow_path.is_file():
                    raise ValueError("Missing workflow: {}".format(relative_path))
                workflow = workflow_path.read_text(encoding="utf-8")
                if target not in workflow:
                    raise ValueError(
                        "{} does not contain configured target {!r}.".format(
                            relative_path,
                            target,
                        )
                    )

    if validate_workflows:
        actual_workflows = {
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in (PROJECT_ROOT / ".github" / "workflows").glob("test*.yml")
        }
        if referenced_workflows != actual_workflows:
            raise ValueError(
                "Workflow inventory differs from test-environments.json: "
                "missing={}, extra={}".format(
                    sorted(actual_workflows - referenced_workflows),
                    sorted(referenced_workflows - actual_workflows),
                )
            )


def natural_list(values, locale):
    if not values:
        raise ValueError("Cannot render an empty environment list.")
    if len(values) == 1:
        return values[0]
    conjunction = "and" if locale == "en" else "y"
    if len(values) == 2:
        return "{} {} {}".format(values[0], conjunction, values[1])
    if locale == "en":
        return "{}, and {}".format(", ".join(values[:-1]), values[-1])
    return "{} y {}".format(", ".join(values[:-1]), values[-1])


def environment_label(environment, locale):
    return "{} {} ({})".format(
        environment["name"][locale],
        environment["version"],
        environment["architecture"],
    )


def render_summary(manifest, locale):
    platforms = natural_list(
        [
            environment_label(environment, locale)
            for environment in manifest["environments"]
        ],
        locale,
    )
    return manifest["summary_templates"][locale].format(
        platforms=platforms,
        python=manifest["runtime"]["display"][locale],
    )


def render_readme_block(manifest):
    return "{}\n\n{}".format(
        render_summary(manifest, "en"),
        manifest["scope_notes"]["en"],
    )


def render_readme_content(source, manifest):
    pattern = re.compile(
        "{}.*?{}".format(re.escape(START_MARKER), re.escape(END_MARKER)),
        re.DOTALL,
    )
    replacement = "{}\n\n{}\n\n{}".format(
        START_MARKER,
        render_readme_block(manifest),
        END_MARKER,
    )
    rendered, count = pattern.subn(replacement, source)
    if count != 1:
        raise ValueError(
            "README.md must contain exactly one generated test-environment block."
        )
    return rendered


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if README wording or workflow references are stale.",
    )
    return parser.parse_args()


def main(check=False):
    manifest = load_manifest()
    validate_manifest(manifest)
    source = README_PATH.read_text(encoding="utf-8")
    expected = render_readme_content(source, manifest)
    if check:
        if source != expected:
            raise SystemExit(
                "README.md test-environment wording is stale; run "
                "python scripts/sync_test_environments.py."
            )
        print("Test environments, workflows, and README.md are synchronized.")
        return 0
    if source == expected:
        print("README.md test-environment wording is already synchronized.")
        return 0
    README_PATH.write_text(expected, encoding="utf-8")
    print("Updated README.md test-environment wording.")
    return 0


if __name__ == "__main__":
    arguments = parse_args()
    raise SystemExit(main(check=arguments.check))

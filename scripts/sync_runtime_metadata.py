#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Generate or verify runtime constants and release-bound README metadata."""

import argparse
import json
import os
from pathlib import Path
import pprint
import re
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    PROJECT_ROOT / "src" / "qzx" / "resources" / "product-manifest.json"
)
LIFECYCLE_PATH = (
    PROJECT_ROOT / "src" / "qzx" / "resources" / "command-lifecycle.json"
)
COMMAND_INDEX_PATH = (
    PROJECT_ROOT / "src" / "qzx" / "resources" / "command-index.json"
)
OUTPUT_PATH = PROJECT_ROOT / "src" / "qzx" / "_build_info.py"
README_PATH = PROJECT_ROOT / "README.md"
_RELEASE_MARKER = re.compile(r"This source release is QZX `[^`\r\n]+`")
_RELEASE_TABLE_ROW = re.compile(
    r"(?m)^(?P<prefix>\| Source release described here \| )"
    r"`[^`\r\n]+`(?P<suffix> \|.*)$"
)
_PIP_INSTALL_COMMAND = re.compile(
    r"(?m)^python -m pip install(?: --pre)? --upgrade qzx$"
)
_OPTIONAL_EXTRA_INSTALL = re.compile(
    r'python -m pip install(?: --pre)? --upgrade "qzx\[(?P<extra>filetype|ai)\]"'
)
_PIPX_INSTALL_COMMAND = re.compile(
    r"(?m)^pipx install(?: --pip-args='--pre')? qzx$"
)
_PIPX_RUN_COMMAND = re.compile(
    r"(?m)^pipx run(?: --pip-args='--pre')? --spec qzx qzx version$"
)
_INSTALL_CHANNEL_PARAGRAPH = re.compile(
    r"(?P<release_line>This source release is QZX `[^`\r\n]+` and requires "
    r"Python `[^`\r\n]+`\.\r?\n)"
    r"(?P<body>.*?)(?=\r?\n\r?\nQZX supports standard CPython)",
    re.DOTALL,
)
_COMMAND_COUNT = re.compile(
    r"\b\d+ canonical commands in the generated command index\b"
)
_EXPECTED_ONBOARDING_STAGES = (
    "first_success",
    "explore",
    "understand",
)


def load_manifest():
    """Load the canonical product manifest once for one synchronization pass."""
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def validated_onboarding(manifest=None):
    """Validate and return the packaged onboarding contract without rewriting it."""
    manifest = manifest or load_manifest()
    onboarding = manifest.get("onboarding")
    urls = manifest.get("urls")
    if not isinstance(onboarding, dict) or onboarding.get("schema_version") != 1:
        raise ValueError("Onboarding must be a schema-version 1 object.")
    if not isinstance(urls, dict):
        raise ValueError("Product URLs must be an object.")
    if onboarding.get("default_risk") != "read_only":
        raise ValueError("Onboarding must remain read-only by default.")

    for key_name in ("documentation_url_key", "security_url_key"):
        url_key = onboarding.get(key_name)
        url = urls.get(url_key) if isinstance(url_key, str) else None
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError(
                f"Onboarding {key_name} must resolve to one HTTPS product URL."
            )

    command_index = json.loads(COMMAND_INDEX_PATH.read_text(encoding="utf-8"))
    if not isinstance(command_index, dict) or command_index.get("schema_version") != 2:
        raise ValueError("Command index must use schema version 2.")
    entries = command_index.get("commands")
    if not isinstance(entries, list):
        raise ValueError("Command index must contain a commands list.")
    command_names = {
        entry.get("name")
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }

    steps = onboarding.get("steps")
    if not isinstance(steps, list) or len(steps) != len(
        _EXPECTED_ONBOARDING_STAGES
    ):
        raise ValueError("Onboarding must contain exactly three canonical steps.")
    for expected_stage, step in zip(
        _EXPECTED_ONBOARDING_STAGES,
        steps,
        strict=True,
    ):
        if not isinstance(step, dict) or step.get("stage") != expected_stage:
            raise ValueError(
                "Onboarding stages must be ordered as first_success, explore, "
                "and understand."
            )
        command = step.get("command")
        if command not in command_names:
            raise ValueError(
                f"Onboarding command {command!r} is not in command-index.json."
            )
        arguments = step.get("arguments")
        if not isinstance(arguments, list) or any(
            not isinstance(argument, str) or not argument.strip()
            for argument in arguments
        ):
            raise ValueError(
                f"Onboarding step {expected_stage!r} has invalid arguments."
            )
        if not isinstance(step.get("machine_output"), bool):
            raise ValueError(
                f"Onboarding step {expected_stage!r} must declare machine_output."
            )
        purpose = step.get("purpose")
        if not isinstance(purpose, dict) or any(
            not isinstance(purpose.get(language), str)
            or not purpose[language].strip()
            for language in ("en", "es")
        ):
            raise ValueError(
                f"Onboarding step {expected_stage!r} must have bilingual purpose."
            )

    return json.loads(json.dumps(onboarding, ensure_ascii=False))


def generated_content(manifest=None):
    """Render the lightweight constants imported during QZX startup."""
    manifest = manifest or load_manifest()
    lifecycle = json.loads(LIFECYCLE_PATH.read_text(encoding="utf-8"))
    onboarding = validated_onboarding(manifest)
    version = manifest["channels"]["development"]["version"]
    attribution = manifest["product"]["attribution"]
    urls = manifest["urls"]
    command_catalog_url = urls[onboarding["documentation_url_key"]]
    security_guide_url = urls[onboarding["security_url_key"]]
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Development version must be non-empty text.")
    if not isinstance(attribution, str) or not attribution.strip():
        raise ValueError("Product attribution must be non-empty text.")
    welcome_entry = lifecycle["commands"]["welcome"]
    stage_name = welcome_entry["stage"]
    stage = lifecycle["stages"][stage_name]
    welcome_maturity = {
        "stage": stage_name,
        "label": stage["label"],
        "sequence": stage["sequence"],
        "public_executable": stage["public_executable"],
        "stability": stage["stability"],
        "summary": stage["summary"],
        "promotion_review_required": stage[
            "promotion_review_required"
        ],
        "assessment_scope": lifecycle["assessment"]["scope"],
    }
    if welcome_entry.get("note"):
        welcome_maturity["note"] = welcome_entry["note"]
    if welcome_entry.get("review"):
        welcome_maturity["review"] = welcome_entry["review"]
    return (
        '"""Generated startup constants; synchronize from product and '
        'lifecycle manifests."""\n\n'
        "VERSION = {}\n"
        "ATTRIBUTION = {}\n"
        "COMMAND_CATALOG_URL = {}\n"
        "SECURITY_GUIDE_URL = {}\n"
        "ONBOARDING = {}\n"
        "WELCOME_MATURITY = {}\n".format(
            json.dumps(version, ensure_ascii=False),
            json.dumps(attribution, ensure_ascii=False),
            json.dumps(command_catalog_url, ensure_ascii=False),
            json.dumps(security_guide_url, ensure_ascii=False),
            pprint.pformat(
                onboarding,
                sort_dicts=False,
                width=79,
            ),
            pprint.pformat(
                welcome_maturity,
                sort_dicts=False,
                width=79,
            ),
        )
    )


def _canonical_command_count() -> int:
    """Return the generated public command count used by release-facing copy."""
    command_index = json.loads(COMMAND_INDEX_PATH.read_text(encoding="utf-8"))
    entries = command_index.get("commands") if isinstance(command_index, dict) else None
    if command_index.get("schema_version") != 2 or not isinstance(entries, list):
        raise ValueError("Command index must use schema version 2 with a commands list.")
    names = [
        entry.get("name")
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    ]
    if len(names) != len(entries) or len(set(names)) != len(names):
        raise ValueError("Command index must contain unique named command entries.")
    return len(names)


def synchronized_readme_content(manifest=None):
    """Project version, install channel, and command inventory into README.md."""
    manifest = manifest or load_manifest()
    published = manifest["channels"]["published"]
    version = published["version"]
    install_command = published["install_command"]
    supported_install_commands = {
        "python -m pip install --upgrade qzx",
        "python -m pip install --pre --upgrade qzx",
    }
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Published version must be non-empty text.")
    if install_command not in supported_install_commands:
        raise ValueError("Published install command is not a supported QZX channel command.")

    prerelease = " --pre " in install_command
    pipx_install = (
        "pipx install --pip-args='--pre' qzx"
        if prerelease
        else "pipx install qzx"
    )
    pipx_run = (
        "pipx run --pip-args='--pre' --spec qzx qzx version"
        if prerelease
        else "pipx run --spec qzx qzx version"
    )
    install_prefix = install_command.rsplit(" qzx", 1)[0]
    channel_paragraph = (
        "A normal `python -m pip install qzx` selects the latest final release; use\n"
        "`--pre` to opt into this Alpha pre-release. PyPI is authoritative for the\n"
        "published package, and `qzx version --json` is authoritative for what is installed."
        if prerelease
        else
        "The published QZX distribution uses pip's normal installation channel while the\n"
        "product itself remains Alpha software. PyPI is authoritative for the published\n"
        "package, and `qzx version --json` is authoritative for what is installed."
    )

    content = README_PATH.read_text(encoding="utf-8")
    marker = f"This source release is QZX `{version}`"
    content, marker_count = _RELEASE_MARKER.subn(marker, content)
    content, table_count = _RELEASE_TABLE_ROW.subn(
        lambda match: f"{match.group('prefix')}`{version}`{match.group('suffix')}",
        content,
    )
    content, pip_count = _PIP_INSTALL_COMMAND.subn(install_command, content)
    content, extra_count = _OPTIONAL_EXTRA_INSTALL.subn(
        lambda match: f'{install_prefix} "qzx[{match.group("extra")}]"',
        content,
    )
    content, pipx_install_count = _PIPX_INSTALL_COMMAND.subn(pipx_install, content)
    content, pipx_run_count = _PIPX_RUN_COMMAND.subn(pipx_run, content)
    content, channel_count = _INSTALL_CHANNEL_PARAGRAPH.subn(
        lambda match: match.group("release_line") + channel_paragraph,
        content,
    )
    content, command_count_updates = _COMMAND_COUNT.subn(
        f"{_canonical_command_count()} canonical commands in the generated command index",
        content,
    )

    expected_counts = {
        "immutable source-release marker": (marker_count, 1),
        "source-release summary row": (table_count, 1),
        "pip install examples": (pip_count, 2),
        "optional-extra install examples": (extra_count, 2),
        "pipx install example": (pipx_install_count, 1),
        "pipx run example": (pipx_run_count, 1),
        "installation-channel paragraph": (channel_count, 1),
        "command-count summary": (command_count_updates, 1),
    }
    mismatches = [
        f"{label}: expected {expected}, found {actual}"
        for label, (actual, expected) in expected_counts.items()
        if actual != expected
    ]
    if mismatches:
        raise ValueError("README.md release projection anchors drifted: " + "; ".join(mismatches))
    return content


def write_atomic(content, path=OUTPUT_PATH, prefix=".build-info-"):
    """Replace one maintained UTF-8 projection without exposing a partial file."""
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=prefix,
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
    finally:
        if temporary_name and os.path.lexists(temporary_name):
            os.unlink(temporary_name)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write every current product-manifest projection.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    manifest = load_manifest()
    projections = (
        (
            OUTPUT_PATH,
            generated_content(manifest),
            ".build-info-",
            "lightweight runtime metadata",
        ),
        (
            README_PATH,
            synchronized_readme_content(manifest),
            ".release-readme-",
            "release-bound README metadata",
        ),
    )

    stale = []
    for path, content, _prefix, label in projections:
        try:
            current = path.read_text(encoding="utf-8")
        except OSError:
            current = None
        if current != content:
            stale.append((path, content, _prefix, label))

    if args.write:
        for path, content, prefix, label in stale:
            write_atomic(content, path=path, prefix=prefix)
            print(f"Wrote {label} to {path}.")
        if not stale:
            print("Runtime and release README metadata are already synchronized.")
        return 0

    if stale:
        labels = ", ".join(item[3] for item in stale)
        print(
            f"Runtime projections are stale ({labels}). Run "
            "'python scripts/sync_runtime_metadata.py --write'.",
            file=sys.stderr,
        )
        return 1
    print("Runtime and release README metadata are synchronized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

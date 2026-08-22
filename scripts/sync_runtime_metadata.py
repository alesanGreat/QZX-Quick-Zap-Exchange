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
OUTPUT_PATH = PROJECT_ROOT / "src" / "qzx" / "_build_info.py"
README_PATH = PROJECT_ROOT / "README.md"
_RELEASE_MARKER = re.compile(r"This source release is QZX `[^`\r\n]+`")
_RELEASE_TABLE_ROW = re.compile(
    r"(?m)^(?P<prefix>\| Source release described here \| )"
    r"`[^`\r\n]+`(?P<suffix> \|.*)$"
)


def load_manifest():
    """Load the canonical product manifest once for one synchronization pass."""
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def generated_content(manifest=None):
    """Render the lightweight constants imported during QZX startup."""
    manifest = manifest or load_manifest()
    lifecycle = json.loads(LIFECYCLE_PATH.read_text(encoding="utf-8"))
    version = manifest["channels"]["development"]["version"]
    attribution = manifest["product"]["attribution"]
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
        "WELCOME_MATURITY = {}\n".format(
            json.dumps(version, ensure_ascii=False),
            json.dumps(attribution, ensure_ascii=False),
            pprint.pformat(
                welcome_maturity,
                sort_dicts=False,
                width=79,
            ),
        )
    )


def synchronized_readme_content(manifest=None):
    """Bind the package README to the manifest's immutable published version."""
    manifest = manifest or load_manifest()
    version = manifest["channels"]["published"]["version"]
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Published version must be non-empty text.")

    content = README_PATH.read_text(encoding="utf-8")
    marker = f"This source release is QZX `{version}`"
    content, marker_count = _RELEASE_MARKER.subn(marker, content)
    content, table_count = _RELEASE_TABLE_ROW.subn(
        lambda match: (
            f"{match.group('prefix')}`{version}`{match.group('suffix')}"
        ),
        content,
    )
    if marker_count != 1:
        raise ValueError(
            "README.md must contain exactly one immutable source-release marker."
        )
    if table_count != 1:
        raise ValueError(
            "README.md must contain exactly one source-release summary row."
        )
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

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Generate or verify the lightweight runtime constants used during startup."""

import argparse
import json
import os
from pathlib import Path
import pprint
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


def generated_content():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
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


def write_atomic(content):
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=".build-info-",
            suffix=".tmp",
            dir=OUTPUT_PATH.parent,
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, OUTPUT_PATH)
        temporary_name = None
    finally:
        if temporary_name and os.path.lexists(temporary_name):
            os.unlink(temporary_name)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the current product-manifest projection.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    content = generated_content()
    if args.write:
        write_atomic(content)
        print("Wrote lightweight runtime metadata to {}.".format(OUTPUT_PATH))
        return 0
    try:
        current = OUTPUT_PATH.read_text(encoding="utf-8")
    except OSError:
        current = None
    if current != content:
        print(
            "Runtime metadata is stale. Run "
            "'python scripts/sync_runtime_metadata.py --write'.",
            file=sys.stderr,
        )
        return 1
    print("Runtime metadata is synchronized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

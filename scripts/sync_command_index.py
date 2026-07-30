#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Generate or verify QZX's packaged lazy command index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_index import (  # noqa: E402
    COMMAND_INDEX_PATH,
    build_command_index,
    write_command_index,
)
from qzx.core.command_loader import CommandLoader  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the current full-discovery projection.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    loader = CommandLoader()
    discovered = loader.discover_commands(validate_index=False)
    document = build_command_index(set(discovered.values()))
    payload = json.dumps(document, ensure_ascii=False, indent=2) + "\n"

    if args.write:
        write_command_index(document)
        print("Wrote {} command entries to {}.".format(
            len(document["commands"]),
            COMMAND_INDEX_PATH,
        ))
        return 0

    try:
        current = COMMAND_INDEX_PATH.read_text(encoding="utf-8")
    except OSError:
        current = None
    if current != payload:
        print(
            "Command index is stale. Run "
            "'python scripts/sync_command_index.py --write'.",
            file=sys.stderr,
        )
        return 1
    print("Command index is synchronized ({} commands).".format(
        len(document["commands"])
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

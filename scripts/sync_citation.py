#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Generate the repository-root CITATION.cff from canonical QZX product facts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_MANIFEST_PATH = PROJECT_ROOT / "src" / "qzx" / "resources" / "product-manifest.json"
OUTPUT_PATH = PROJECT_ROOT / "CITATION.cff"

KEYWORDS = (
    "AI agents",
    "automation",
    "command-line interface",
    "cross-platform",
    "structured JSON",
    "JSON Schema",
    "QZX Result Contract",
    "Model Context Protocol",
    "interoperability",
)


def load_product_manifest() -> dict[str, Any]:
    with PRODUCT_MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported QZX product manifest schema version.")
    return manifest


def _quoted(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_citation(manifest: dict[str, Any]) -> str:
    product = manifest["product"]
    urls = manifest["urls"]
    published = manifest["channels"]["published"]
    author_name = str(product["author"]["name"])
    given_name, family_name = author_name.split(" ", 1)

    lines = [
        "cff-version: 1.2.0",
        'message: "If you use QZX, please cite the software and its creator."',
        f"title: {_quoted(product['full_name'])}",
        "type: software",
        'abstract: "A predictable cross-platform command layer and open JSON result contract for AI agents and automation."',
        "authors:",
        f"  - family-names: {_quoted(family_name)}",
        f"    given-names: {_quoted(given_name)}",
        '    email: "qzx@yumbale.com"',
        f"version: {_quoted(published['version'])}",
        f"date-released: {_quoted(published['released_at'])}",
        f"repository-code: {_quoted(urls['repository'])}",
        f"url: {_quoted(urls['site_origin'] + '/en/')}",
        f"license: {_quoted(product['license'])}",
        "keywords:",
    ]
    lines.extend(f"  - {_quoted(keyword)}" for keyword in KEYWORDS)
    return "\n".join(lines) + "\n"


def sync(*, check: bool) -> bool:
    expected = render_citation(load_product_manifest())
    actual = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else None
    if actual == expected:
        print("CITATION.cff is synchronized with product-manifest.json.")
        return True
    if check:
        print("CITATION.cff is stale or missing.")
        return False
    OUTPUT_PATH.write_text(expected, encoding="utf-8", newline="\n")
    print("CITATION.cff synchronized with product-manifest.json.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail instead of rewriting when CITATION.cff is stale or missing.",
    )
    arguments = parser.parse_args()
    return 0 if sync(check=arguments.check) else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Generate the repository-root CodeMeta 3.1 projection from QZX product facts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_MANIFEST_PATH = PROJECT_ROOT / "src" / "qzx" / "resources" / "product-manifest.json"
OUTPUT_PATH = PROJECT_ROOT / "codemeta.json"
CODEMETA_CONTEXT = "https://w3id.org/codemeta/3.1"
PERSON_ID = "https://qzx.yumbale.com/#alejandro-sanchez"


def load_product_manifest() -> dict[str, Any]:
    with PRODUCT_MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported QZX product manifest schema version.")
    return manifest


def build_codemeta(manifest: dict[str, Any]) -> dict[str, Any]:
    product = manifest["product"]
    urls = manifest["urls"]
    published = manifest["channels"]["published"]
    author = product["author"]
    author_name = str(author["name"])
    given_name, family_name = author_name.split(" ", 1)

    return {
        "@context": CODEMETA_CONTEXT,
        "@type": "SoftwareSourceCode",
        "name": product["full_name"],
        "description": product["description"]["en"],
        "applicationCategory": "DeveloperApplication",
        "applicationSubCategory": "Command-line interface",
        "author": {
            "@id": PERSON_ID,
            "@type": "Person",
            "name": author_name,
            "givenName": given_name,
            "familyName": family_name,
            "email": "qzx@yumbale.com",
            "url": author["profile_url"],
            "sameAs": author["same_as"],
        },
        "maintainer": PERSON_ID,
        "codeRepository": urls["repository"],
        "issueTracker": urls["issues"],
        "continuousIntegration": urls["repository"] + "/actions",
        "license": product["license_url"],
        "version": published["version"],
        "datePublished": published["released_at"],
        "developmentStatus": "active",
        "programmingLanguage": "Python",
        "runtimePlatform": "CPython 3.13; Python >=3.13",
        "operatingSystem": product["platforms"],
        "isAccessibleForFree": product["pricing"]["free_to_use"],
        "url": urls["site_origin"] + "/",
        "installUrl": urls["package"],
        "readme": urls["repository"] + "/blob/main/README.md",
        "releaseNotes": urls["changelog"],
        "relatedLink": [
            urls["result_contract"],
            urls["golden_core"],
            urls["compatibility"],
            urls["security"],
        ],
        "keywords": [
            "QZX",
            "QZX Result Contract",
            "AI agents",
            "automation",
            "command-line interface",
            "cross-platform",
            "structured JSON",
            "JSON Schema",
            "Model Context Protocol",
            "interoperability",
        ],
    }


def render_codemeta(manifest: dict[str, Any]) -> str:
    return json.dumps(build_codemeta(manifest), indent=2, ensure_ascii=False) + "\n"


def sync(*, check: bool) -> bool:
    expected = render_codemeta(load_product_manifest())
    actual = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else None
    if actual == expected:
        print("codemeta.json is synchronized with product-manifest.json.")
        return True
    if check:
        print("codemeta.json is stale or missing.")
        return False
    OUTPUT_PATH.write_text(expected, encoding="utf-8", newline="\n")
    print("codemeta.json synchronized with product-manifest.json.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail instead of rewriting when codemeta.json is stale or missing.",
    )
    arguments = parser.parse_args()
    return 0 if sync(check=arguments.check) else 1


if __name__ == "__main__":
    raise SystemExit(main())

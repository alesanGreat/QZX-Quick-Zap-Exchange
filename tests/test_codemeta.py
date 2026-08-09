#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for QZX CodeMeta attribution and discovery metadata."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CITATION_PATH = REPOSITORY_ROOT / "CITATION.cff"
CITATION_SYNC_SCRIPT = REPOSITORY_ROOT / "scripts" / "sync_citation.py"
CODEMETA_PATH = REPOSITORY_ROOT / "codemeta.json"
SYNC_SCRIPT = REPOSITORY_ROOT / "scripts" / "sync_codemeta.py"
PRODUCT_MANIFEST_PATH = (
    REPOSITORY_ROOT / "src" / "qzx" / "resources" / "product-manifest.json"
)

citation_spec = importlib.util.spec_from_file_location(
    "qzx_sync_citation", CITATION_SYNC_SCRIPT
)
sync_citation = importlib.util.module_from_spec(citation_spec)
assert citation_spec.loader is not None
citation_spec.loader.exec_module(sync_citation)

codemeta_spec = importlib.util.spec_from_file_location("qzx_sync_codemeta", SYNC_SCRIPT)
sync_codemeta = importlib.util.module_from_spec(codemeta_spec)
assert codemeta_spec.loader is not None
codemeta_spec.loader.exec_module(sync_codemeta)


def test_codemeta_matches_canonical_product_manifest():
    product_manifest = json.loads(PRODUCT_MANIFEST_PATH.read_text(encoding="utf-8"))
    actual = json.loads(CODEMETA_PATH.read_text(encoding="utf-8"))
    expected = sync_codemeta.build_codemeta(product_manifest)

    assert actual == expected
    assert actual["@context"] == "https://w3id.org/codemeta/3.1"
    assert actual["@type"] == "SoftwareSourceCode"
    assert actual["name"] == "QZX — Quick Zap Exchange"
    assert actual["version"] == product_manifest["channels"]["published"]["version"]
    assert actual["datePublished"] == product_manifest["channels"]["published"]["released_at"]
    assert actual["operatingSystem"] == product_manifest["product"]["platforms"]
    assert actual["isAccessibleForFree"] is True


def test_codemeta_credits_alejandro_without_invented_identifiers():
    actual = json.loads(CODEMETA_PATH.read_text(encoding="utf-8"))
    author = actual["author"]

    assert author == {
        "@id": "https://qzx.yumbale.com/#alejandro-sanchez",
        "@type": "Person",
        "name": "Alejandro Sánchez",
        "givenName": "Alejandro",
        "familyName": "Sánchez",
        "email": "qzx@yumbale.com",
        "url": "https://qzx.yumbale.com/en/alejandro-sanchez",
        "sameAs": [
            "https://github.com/alesanGreat",
            "https://pypi.org/user/alesanGreat/",
            "https://www.linkedin.com/in/alesan/",
        ],
    }
    assert actual["maintainer"] == author["@id"]
    assert "identifier" not in author
    assert "affiliation" not in author
    assert "referencePublication" not in actual


def test_codemeta_uses_only_intended_codemeta_31_terms():
    actual = json.loads(CODEMETA_PATH.read_text(encoding="utf-8"))
    assert set(actual) == {
        "@context",
        "@type",
        "name",
        "description",
        "applicationCategory",
        "applicationSubCategory",
        "author",
        "maintainer",
        "codeRepository",
        "issueTracker",
        "continuousIntegration",
        "license",
        "version",
        "datePublished",
        "developmentStatus",
        "programmingLanguage",
        "runtimePlatform",
        "operatingSystem",
        "isAccessibleForFree",
        "url",
        "installUrl",
        "readme",
        "releaseNotes",
        "relatedLink",
        "keywords",
    }
    assert set(actual["author"]) == {
        "@id",
        "@type",
        "name",
        "givenName",
        "familyName",
        "email",
        "url",
        "sameAs",
    }


def test_codemeta_links_result_contract_and_machine_discovery_surfaces():
    actual = json.loads(CODEMETA_PATH.read_text(encoding="utf-8"))

    assert actual["codeRepository"] == "https://github.com/alesanGreat/QZX-Quick-Zap-Exchange"
    assert actual["continuousIntegration"].endswith("/actions")
    assert actual["issueTracker"].endswith("/issues")
    assert "https://qzx.yumbale.com/en/result-contract" in actual["relatedLink"]
    assert "QZX Result Contract" in actual["keywords"]
    assert "Model Context Protocol" in actual["keywords"]


def test_citation_and_codemeta_tell_the_same_attribution_story():
    product_manifest = json.loads(PRODUCT_MANIFEST_PATH.read_text(encoding="utf-8"))
    citation = CITATION_PATH.read_text(encoding="utf-8")
    actual = json.loads(CODEMETA_PATH.read_text(encoding="utf-8"))

    assert citation == sync_citation.render_citation(product_manifest)
    assert 'given-names: "Alejandro"' in citation
    assert 'family-names: "Sánchez"' in citation
    assert f'version: "{actual["version"]}"' in citation
    assert f'date-released: "{actual["datePublished"]}"' in citation
    assert '  - "QZX Result Contract"' in citation
    assert '  - "Model Context Protocol"' in citation


def test_attribution_check_modes_pass_without_rewriting():
    before_citation = CITATION_PATH.read_bytes()
    before_codemeta = CODEMETA_PATH.read_bytes()

    citation_process = subprocess.run(
        [sys.executable, str(CITATION_SYNC_SCRIPT), "--check"],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    codemeta_process = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT), "--check"],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert citation_process.returncode == 0, citation_process.stderr
    assert codemeta_process.returncode == 0, codemeta_process.stderr
    assert "is synchronized" in citation_process.stdout
    assert "is synchronized" in codemeta_process.stdout
    assert CITATION_PATH.read_bytes() == before_citation
    assert CODEMETA_PATH.read_bytes() == before_codemeta

"""Regression tests for QZX release-artifact verification."""

from __future__ import annotations

import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts.verify_distribution_artifacts import (
    ATTRIBUTION,
    CONFORMANCE_RECEIPT_SCHEMA_ID,
    CONFORMANCE_RECEIPT_WHEEL_PATH,
    GOLDEN_CORE_WHEEL_PATH,
    RESULT_CONTRACT_EXAMPLE_SUFFIXES,
    RESULT_CONTRACT_SCHEMA_ID,
    RESULT_CONTRACT_WHEEL_PATH,
    canonical_readme_relative_files,
    release_readme_marker,
    verify_distributions,
)


VERSION = "9.8.7a6"
REQUIRES_PYTHON = ">=3.13"
RESULT_CONTRACT_SCHEMA = (
    '{"$schema":"https://json-schema.org/draft/2020-12/schema",'
    f'"$id":"{RESULT_CONTRACT_SCHEMA_ID}",'
    '"required":["success","message"],'
    '"additionalProperties":true}'
)
GOLDEN_CORE_COMMANDS = [
    "version",
    "listCommands",
    "help",
    "getCurrentDateTime",
    "getCurrentDirectory",
    "getSystemInfo",
    "getDiskSpace",
    "getRamInfo",
    "listFiles",
    "findFiles",
    "findText",
    "calculateFileHash",
    "getGitStatus",
    "diagnoseProject",
    "checkUrlStatus",
]
GOLDEN_CORE_REGISTRY = json.dumps({
    "schema_version": 1,
    "name": "QZX Golden Core",
    "status": "candidate",
    "target_maturity": "beta",
    "commands": [
        {"name": name}
        for name in GOLDEN_CORE_COMMANDS
    ],
})
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE_RECEIPT_SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "src"
    / "qzx"
    / "resources"
    / "schemas"
    / "result-contract-conformance-receipt-v1.schema.json"
)
CONFORMANCE_RECEIPT_SCHEMA = CONFORMANCE_RECEIPT_SCHEMA_PATH.read_text(
    encoding="utf-8"
)
CONFORMANCE_MANIFEST_PATH = (
    REPOSITORY_ROOT / "examples" / "result_contract" / "manifest.json"
)
CONFORMANCE_DOCUMENT = json.loads(
    CONFORMANCE_MANIFEST_PATH.read_text(encoding="utf-8")
)
CONFORMANCE_CASES = [
    (case["id"], case["file"], case["expected_conformant"])
    for case in CONFORMANCE_DOCUMENT["cases"]
]


def metadata_text(description_version=VERSION) -> str:
    return (
        "Metadata-Version: 2.4\n"
        "Name: qzx\n"
        f"Version: {VERSION}\n"
        f"Requires-Python: {REQUIRES_PYTHON}\n"
        "Description-Content-Type: text/markdown\n"
        "\n"
        f"{ATTRIBUTION}\n\n"
        f"{release_readme_marker(description_version)}.\n"
    )


def add_tar_text(archive, name, text, mode=0o644):
    payload = text.encode("utf-8")
    member = tarfile.TarInfo(name)
    member.size = len(payload)
    member.mode = mode
    archive.addfile(member, io.BytesIO(payload))


def build_fixture_distributions(
    dist_dir,
    launcher_mode=0o755,
    description_version=VERSION,
    omitted_support_file=None,
):
    wheel = dist_dir / f"qzx-{VERSION}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            f"qzx-{VERSION}.dist-info/METADATA",
            metadata_text(description_version),
        )
        archive.writestr(
            RESULT_CONTRACT_WHEEL_PATH,
            RESULT_CONTRACT_SCHEMA,
        )
        archive.writestr(
            CONFORMANCE_RECEIPT_WHEEL_PATH,
            CONFORMANCE_RECEIPT_SCHEMA,
        )
        archive.writestr(
            GOLDEN_CORE_WHEEL_PATH,
            GOLDEN_CORE_REGISTRY,
        )

    sdist = dist_dir / f"qzx-{VERSION}.tar.gz"
    root = f"qzx-{VERSION}"
    with tarfile.open(sdist, "w:gz") as archive:
        add_tar_text(
            archive,
            f"{root}/PKG-INFO",
            metadata_text(description_version),
        )
        add_tar_text(
            archive,
            f"{root}/README.md",
            f"{ATTRIBUTION}\n\n{release_readme_marker(description_version)}.\n",
        )
        add_tar_text(
            archive,
            f"{root}/qzx.sh",
            "#!/bin/sh\n",
            mode=launcher_mode,
        )
        add_tar_text(
            archive,
            f"{root}/src/qzx/resources/schemas/result-contract-v1.schema.json",
            RESULT_CONTRACT_SCHEMA,
        )
        add_tar_text(
            archive,
            (
                f"{root}/src/qzx/resources/schemas/"
                "result-contract-conformance-receipt-v1.schema.json"
            ),
            CONFORMANCE_RECEIPT_SCHEMA,
        )
        add_tar_text(
            archive,
            f"{root}/src/qzx/resources/golden-core.json",
            GOLDEN_CORE_REGISTRY,
        )
        support_files = sorted(set(canonical_readme_relative_files()) | {
            "ADOPTERS.md",
            "CITATION.cff",
            "action.yml",
            "codemeta.json",
            "docs/golden-core.md",
            "docs/result-contract-v1.md",
            "docs/result-contract-adoption.md",
            "docs/result-contract-quickstart.md",
            "scripts/sync_citation.py",
            "scripts/sync_codemeta.py",
            "scripts/validate_result_contract.py",
            "scripts/validate_mcp_result_contract.py",
            "scripts/validate_result_contract_evidence.py",
            "scripts/run_result_contract_conformance.py",
            "scripts/verify_golden_core.py",
            "scripts/capture_golden_core_platform_evidence.py",
            "scripts/merge_golden_core_platform_evidence.py",
            ".github/actions/result-contract-conformance/action.yml",
            ".github/actions/result-contract-conformance/run.py",
            ".github/actions/result-contract-conformance/README.md",
        })
        for relative_path in support_files:
            if relative_path == omitted_support_file:
                continue
            add_tar_text(
                archive,
                f"{root}/{relative_path}",
                (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8"),
            )
        examples_root = REPOSITORY_ROOT / "examples" / "result_contract"
        for source in sorted(examples_root.rglob("*")):
            relative_path = source.relative_to(REPOSITORY_ROOT).as_posix()
            if (
                not source.is_file()
                or source.suffix.lower() not in RESULT_CONTRACT_EXAMPLE_SUFFIXES
                or relative_path == omitted_support_file
            ):
                continue
            add_tar_text(
                archive,
                f"{root}/{relative_path}",
                source.read_text(encoding="utf-8"),
            )
    return wheel, sdist


def test_distribution_verifier_accepts_executable_posix_launcher(tmp_path):
    build_fixture_distributions(tmp_path)

    result = verify_distributions(
        tmp_path,
        expected_version=VERSION,
        expected_python=REQUIRES_PYTHON,
    )

    assert result["success"] is True
    assert result["version"] == VERSION
    assert len(result["artifacts"]) == 2
    assert all(
        artifact["result_contract_schema"] == RESULT_CONTRACT_SCHEMA_ID
        for artifact in result["artifacts"]
    )
    assert all(
        artifact["conformance_receipt_schema"] == CONFORMANCE_RECEIPT_SCHEMA_ID
        for artifact in result["artifacts"]
    )
    assert all(
        artifact["golden_core_commands"] == 15
        for artifact in result["artifacts"]
    )
    assert result["artifacts"][1]["qzx_sh_mode"] == "0755"
    assert (
        result["artifacts"][1]["result_contract_conformance_cases"]
        == len(CONFORMANCE_CASES)
    )


def test_distribution_verifier_rejects_windows_sdist_launcher_mode(tmp_path):
    build_fixture_distributions(tmp_path, launcher_mode=0o666)

    with pytest.raises(ValueError, match=r"qzx\.sh as 0666.*require 0755"):
        verify_distributions(
            tmp_path,
            expected_version=VERSION,
            expected_python=REQUIRES_PYTHON,
        )


def test_distribution_verifier_rejects_missing_readme_link_target(tmp_path):
    build_fixture_distributions(
        tmp_path,
        omitted_support_file="SPONSORSHIP.md",
    )

    with pytest.raises(
        ValueError,
        match=r"missing required release files: .*SPONSORSHIP\.md",
    ):
        verify_distributions(
            tmp_path,
            expected_version=VERSION,
            expected_python=REQUIRES_PYTHON,
        )


@pytest.mark.parametrize(
    ("omitted_support_file", "missing_pattern"),
    [
        (
            "examples/result_contract/mcp-python-sdk-v2/requirements.txt",
            r"mcp-python-sdk-v2/requirements\.txt",
        ),
        (
            "examples/result_contract/mcp-go-sdk-v1/go.sum",
            r"mcp-go-sdk-v1/go\.sum",
        ),
    ],
)
def test_distribution_verifier_rejects_missing_nested_result_contract_example(
    tmp_path,
    omitted_support_file,
    missing_pattern,
):
    build_fixture_distributions(
        tmp_path,
        omitted_support_file=omitted_support_file,
    )

    with pytest.raises(
        ValueError,
        match=rf"missing required release files: .*{missing_pattern}",
    ):
        verify_distributions(
            tmp_path,
            expected_version=VERSION,
            expected_python=REQUIRES_PYTHON,
        )


def test_distribution_verifier_rejects_stale_packaged_description(tmp_path):
    build_fixture_distributions(tmp_path, description_version="9.8.7a5")

    with pytest.raises(
        ValueError,
        match="does not identify its immutable source release",
    ):
        verify_distributions(
            tmp_path,
            expected_version=VERSION,
            expected_python=REQUIRES_PYTHON,
        )

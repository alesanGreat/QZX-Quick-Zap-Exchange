"""Regression tests for QZX release-artifact verification."""

from __future__ import annotations

import io
import json
import tarfile
import zipfile

import pytest

from scripts.verify_distribution_artifacts import (
    ATTRIBUTION,
    GOLDEN_CORE_WHEEL_PATH,
    RESULT_CONTRACT_SCHEMA_ID,
    RESULT_CONTRACT_WHEEL_PATH,
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
CONFORMANCE_CASES = [
    ("valid_success", "valid-success.json", True),
    ("valid_failure", "valid-failure.json", True),
    ("invalid_missing_message", "invalid-missing-message.json", False),
    ("invalid_success_string", "invalid-success-string.json", False),
    (
        "invalid_failure_without_error",
        "invalid-failure-without-error.json",
        False,
    ),
]
CONFORMANCE_MANIFEST = json.dumps({
    "schema_version": 1,
    "contract": RESULT_CONTRACT_SCHEMA_ID,
    "cases": [
        {
            "id": case_id,
            "file": filename,
            "expected_conformant": expected,
            "expected_violations": [],
        }
        for case_id, filename, expected in CONFORMANCE_CASES
    ],
})


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
            f"{root}/docs/result-contract-v1.md",
            "# QZX Result Contract v1\n",
        )
        add_tar_text(
            archive,
            f"{root}/scripts/validate_result_contract.py",
            "#!/usr/bin/env python\n",
        )
        add_tar_text(
            archive,
            f"{root}/src/qzx/resources/golden-core.json",
            GOLDEN_CORE_REGISTRY,
        )
        add_tar_text(
            archive,
            f"{root}/docs/golden-core.md",
            "# QZX Golden Core\n",
        )
        add_tar_text(
            archive,
            f"{root}/docs/result-contract-adoption.md",
            "# Adopting QZX Result Contract v1\n",
        )
        add_tar_text(
            archive,
            f"{root}/ADOPTERS.md",
            "# QZX Result Contract adopters\n",
        )
        add_tar_text(
            archive,
            f"{root}/scripts/run_result_contract_conformance.py",
            "#!/usr/bin/env python\n",
        )
        add_tar_text(
            archive,
            f"{root}/scripts/verify_golden_core.py",
            "#!/usr/bin/env python\n",
        )
        add_tar_text(
            archive,
            f"{root}/scripts/capture_golden_core_platform_evidence.py",
            "#!/usr/bin/env python\n",
        )
        add_tar_text(
            archive,
            f"{root}/scripts/merge_golden_core_platform_evidence.py",
            "#!/usr/bin/env python\n",
        )
        add_tar_text(
            archive,
            f"{root}/examples/result_contract/manifest.json",
            CONFORMANCE_MANIFEST,
        )
        for _, filename, _ in CONFORMANCE_CASES:
            add_tar_text(
                archive,
                f"{root}/examples/result_contract/{filename}",
                '{"success":true,"message":"fixture"}',
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
        artifact["golden_core_commands"] == 15
        for artifact in result["artifacts"]
    )
    assert result["artifacts"][1]["qzx_sh_mode"] == "0755"
    assert (
        result["artifacts"][1]["result_contract_conformance_cases"]
        == 5
    )


def test_distribution_verifier_rejects_windows_sdist_launcher_mode(tmp_path):
    build_fixture_distributions(tmp_path, launcher_mode=0o666)

    with pytest.raises(ValueError, match=r"qzx\.sh as 0666.*require 0755"):
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

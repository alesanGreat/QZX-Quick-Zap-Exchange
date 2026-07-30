"""Regression tests for QZX release-artifact verification."""

from __future__ import annotations

import io
import tarfile
import zipfile

import pytest

from scripts.verify_distribution_artifacts import (
    ATTRIBUTION,
    verify_distributions,
)


VERSION = "0.2.2.0.6a8"
REQUIRES_PYTHON = ">=3.13"


def metadata_text() -> str:
    return (
        "Metadata-Version: 2.4\n"
        "Name: qzx\n"
        f"Version: {VERSION}\n"
        f"Requires-Python: {REQUIRES_PYTHON}\n"
        "Description-Content-Type: text/markdown\n"
        "\n"
        f"{ATTRIBUTION}\n"
    )


def add_tar_text(archive, name, text, mode=0o644):
    payload = text.encode("utf-8")
    member = tarfile.TarInfo(name)
    member.size = len(payload)
    member.mode = mode
    archive.addfile(member, io.BytesIO(payload))


def build_fixture_distributions(dist_dir, launcher_mode=0o755):
    wheel = dist_dir / f"qzx-{VERSION}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            f"qzx-{VERSION}.dist-info/METADATA",
            metadata_text(),
        )

    sdist = dist_dir / f"qzx-{VERSION}.tar.gz"
    root = f"qzx-{VERSION}"
    with tarfile.open(sdist, "w:gz") as archive:
        add_tar_text(archive, f"{root}/PKG-INFO", metadata_text())
        add_tar_text(archive, f"{root}/README.md", ATTRIBUTION)
        add_tar_text(
            archive,
            f"{root}/qzx.sh",
            "#!/bin/sh\n",
            mode=launcher_mode,
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
    assert result["artifacts"][1]["qzx_sh_mode"] == "0755"


def test_distribution_verifier_rejects_windows_sdist_launcher_mode(tmp_path):
    build_fixture_distributions(tmp_path, launcher_mode=0o666)

    with pytest.raises(ValueError, match=r"qzx\.sh as 0666.*require 0755"):
        verify_distributions(
            tmp_path,
            expected_version=VERSION,
            expected_python=REQUIRES_PYTHON,
        )

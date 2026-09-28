"""Regression tests for cross-platform source-distribution archive metadata."""

from __future__ import annotations

import hashlib
import io
import tarfile

from scripts.sdist_release_archive import normalize_sdist_launcher_mode


def _add_text(archive, name, text, mode):
    payload = text.encode("utf-8")
    member = tarfile.TarInfo(name)
    member.mode = mode
    member.size = len(payload)
    archive.addfile(member, io.BytesIO(payload))


def _build_sdist(path, launcher_mode):
    with tarfile.open(path, "w:gz") as archive:
        _add_text(archive, "qzx-1.2.3/qzx.sh", "#!/bin/sh\n", launcher_mode)
        _add_text(archive, "qzx-1.2.3/README.md", "QZX\n", 0o644)


def test_normalizer_repairs_windows_launcher_mode_without_changing_payload(tmp_path):
    archive_path = tmp_path / "qzx-1.2.3.tar.gz"
    _build_sdist(archive_path, 0o666)

    assert normalize_sdist_launcher_mode(archive_path) is True

    with tarfile.open(archive_path, "r:gz") as archive:
        launcher = archive.getmember("qzx-1.2.3/qzx.sh")
        readme = archive.getmember("qzx-1.2.3/README.md")
        assert launcher.mode & 0o777 == 0o755
        assert readme.mode & 0o777 == 0o644
        assert archive.extractfile(launcher).read() == b"#!/bin/sh\n"
        assert archive.extractfile(readme).read() == b"QZX\n"


def test_normalizer_leaves_already_valid_sdist_byte_for_byte_unchanged(tmp_path):
    archive_path = tmp_path / "qzx-1.2.3.tar.gz"
    _build_sdist(archive_path, 0o755)
    before = hashlib.sha256(archive_path.read_bytes()).digest()

    assert normalize_sdist_launcher_mode(archive_path) is False

    assert hashlib.sha256(archive_path.read_bytes()).digest() == before

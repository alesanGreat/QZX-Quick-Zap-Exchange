"""Contract tests for shared safe path-operation primitives."""

import os
from pathlib import Path

from qzx.core.path_operation_utils import (
    destination_device,
    file_sha256,
    is_filesystem_root,
    same_or_nested_path_relationship,
)


def test_path_relationships_distinguish_overlap(tmp_path):
    source = tmp_path / "source"
    source.mkdir()

    assert same_or_nested_path_relationship(source, source) == "same"
    assert (
        same_or_nested_path_relationship(source, source / "child")
        == "destination_within_source"
    )
    assert (
        same_or_nested_path_relationship(source / "child", source)
        == "source_within_destination"
    )
    assert (
        same_or_nested_path_relationship(source, tmp_path / "sibling")
        == "separate"
    )


def test_filesystem_root_detection_is_platform_native(tmp_path):
    assert is_filesystem_root(Path(tmp_path.anchor)) is True
    assert is_filesystem_root(tmp_path) is False


def test_destination_device_uses_nearest_existing_parent(tmp_path):
    destination = tmp_path / "missing" / "nested" / "file.txt"

    assert destination_device(destination) == os.stat(tmp_path).st_dev


def test_file_sha256_is_content_stable(tmp_path):
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    first.write_bytes(b"QZX\0content")
    second.write_bytes(b"QZX\0content")

    assert file_sha256(first) == file_sha256(second)
    assert len(file_sha256(first)) == 64

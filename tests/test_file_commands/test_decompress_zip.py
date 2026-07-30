import zipfile

from qzx.commands.file.decompress_zip import DecompressZipCommand


def test_missing_zip_path():
    result = DecompressZipCommand().execute("")

    assert result["success"] is False
    assert result["error_code"] == "zip_path_required"


def test_nonexistent_zip():
    result = DecompressZipCommand().execute("non_existent_archive.zip")

    assert result["success"] is False
    assert result["error_code"] == "zip_not_found"


def test_invalid_zip(tmp_path):
    bad_zip = tmp_path / "not_a_zip.zip"
    bad_zip.write_text("just text contents", encoding="utf-8")

    result = DecompressZipCommand().execute(str(bad_zip))

    assert result["success"] is False
    assert result["error_code"] == "invalid_zip"


def test_decompress_stages_then_commits_valid_archive(tmp_path):
    zip_file = tmp_path / "test.zip"
    target_dir = tmp_path / "extracted"
    with zipfile.ZipFile(zip_file, "w") as archive:
        archive.writestr("file1.txt", "A" * 100)
        archive.writestr("sub/file2.txt", "B" * 200)

    result = DecompressZipCommand().execute(str(zip_file), str(target_dir))

    assert result["success"] is True
    assert result["files_extracted"] == 2
    assert result["total_bytes_extracted"] == 300
    assert (target_dir / "file1.txt").read_text(encoding="utf-8") == "A" * 100
    assert (target_dir / "sub" / "file2.txt").read_text(
        encoding="utf-8"
    ) == "B" * 200


def test_unsafe_member_aborts_whole_archive(tmp_path):
    zip_file = tmp_path / "unsafe.zip"
    target_dir = tmp_path / "extracted"
    with zipfile.ZipFile(zip_file, "w") as archive:
        archive.writestr("safe.txt", "safe")
        archive.writestr("../outside.txt", "malicious")

    result = DecompressZipCommand().execute(str(zip_file), str(target_dir))

    assert result["success"] is False
    assert result["error_code"] == "unsafe_archive_member"
    assert not target_dir.exists()
    assert not (tmp_path / "outside.txt").exists()


def test_existing_file_blocks_entire_extraction_by_default(tmp_path):
    zip_file = tmp_path / "conflict.zip"
    target_dir = tmp_path / "extracted"
    target_dir.mkdir()
    existing = target_dir / "existing.txt"
    existing.write_text("keep", encoding="utf-8")
    with zipfile.ZipFile(zip_file, "w") as archive:
        archive.writestr("existing.txt", "replace")
        archive.writestr("new.txt", "new")

    result = DecompressZipCommand().execute(str(zip_file), str(target_dir))

    assert result["success"] is False
    assert result["error_code"] == "destination_conflict"
    assert existing.read_text(encoding="utf-8") == "keep"
    assert not (target_dir / "new.txt").exists()


def test_public_overwrite_backs_up_target_before_replacement(
    tmp_path,
    monkeypatch,
):
    zip_file = tmp_path / "conflict.zip"
    target_dir = tmp_path / "extracted"
    backups = tmp_path / "backups"
    target_dir.mkdir()
    existing = target_dir / "existing.txt"
    existing.write_text("keep", encoding="utf-8")
    with zipfile.ZipFile(zip_file, "w") as archive:
        archive.writestr("existing.txt", "replace")
        archive.writestr("new.txt", "new")
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(backups))

    result = DecompressZipCommand().invoke(
        [str(zip_file), str(target_dir), "--overwrite"]
    )

    assert result["success"] is True
    assert result["files_replaced"] == 1
    assert existing.read_text(encoding="utf-8") == "replace"
    assert (target_dir / "new.txt").read_text(encoding="utf-8") == "new"
    backup_path = result["meta"]["safety_backup"]["path"]
    with zipfile.ZipFile(backup_path) as backup:
        assert backup.read("extracted/existing.txt").decode("utf-8") == "keep"


def test_declared_limits_block_extraction(tmp_path):
    zip_file = tmp_path / "many.zip"
    target_dir = tmp_path / "extracted"
    with zipfile.ZipFile(zip_file, "w") as archive:
        archive.writestr("one.txt", "one")
        archive.writestr("two.txt", "two")

    result = DecompressZipCommand().execute(
        str(zip_file),
        str(target_dir),
        max_files=1,
    )

    assert result["success"] is False
    assert result["error_code"] == "archive_file_limit_exceeded"
    assert not target_dir.exists()

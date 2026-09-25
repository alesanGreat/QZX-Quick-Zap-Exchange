"""Immutable artifact snapshot and archive creation for ``deployProject``."""

import hashlib
import io
import os
import stat
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import secrets


def unsafe_artifact_entry(command, artifact, entry, kind):
    relative = entry.relative_to(artifact)
    return command._failure(
        "unsafe_artifact_entry",
        f"Artifact entry '{relative}' is a {kind}. Deployments accept only real directories and regular files.",
        artifact_path=str(artifact), entry=str(relative), entry_kind=kind,
    )


def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _directory_entries(command, artifact, root_path, names, directories):
    for name in list(names):
        path = root_path / name
        relative = path.relative_to(artifact).as_posix()
        if "\\" in relative or "\n" in relative or "\r" in relative or relative == command._manifest_name:
            return command._unsafe_artifact_entry(artifact, path, "unsupported or reserved directory name")
        if path.is_symlink():
            return command._unsafe_artifact_entry(artifact, path, "symbolic link")
        if not stat.S_ISDIR(path.stat(follow_symlinks=False).st_mode):
            return command._unsafe_artifact_entry(artifact, path, "non-directory entry")
        directories.append(path)
    return None


def _file_entries(command, artifact, root_path, names, files, aggregate):
    added_bytes = 0
    for name in names:
        path = root_path / name
        relative = path.relative_to(artifact).as_posix()
        if "\\" in relative or "\n" in relative or "\r" in relative or relative == command._manifest_name:
            return 0, command._unsafe_artifact_entry(artifact, path, "unsupported or reserved file name")
        if path.is_symlink():
            return 0, command._unsafe_artifact_entry(artifact, path, "symbolic link")
        metadata = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode):
            return 0, command._unsafe_artifact_entry(artifact, path, "non-regular file")
        digest, size = command._hash_file(path), metadata.st_size
        files.append({"path": path, "relative": relative, "sha256": digest, "bytes": size})
        added_bytes += size
        aggregate.update(relative.encode("utf-8") + b"\0" + str(size).encode("ascii") + b"\0" + bytes.fromhex(digest))
    return added_bytes, None


def snapshot_artifact(command, artifact):
    files, directories, total = [], [], 0
    aggregate = hashlib.sha256()
    for root, directory_names, file_names in os.walk(artifact, topdown=True, followlinks=False):
        directory_names.sort()
        file_names.sort()
        root_path = Path(root)
        failure = _directory_entries(command, artifact, root_path, directory_names, directories)
        if failure:
            return failure
        added, failure = _file_entries(command, artifact, root_path, file_names, files, aggregate)
        if failure:
            return failure
        total += added
    if not files:
        return command._failure("empty_artifact", f"Artifact '{artifact}' contains no regular files. QZX will not replace a remote release with an empty artifact.", artifact_path=str(artifact))
    return {
        "success": True, "files": files,
        "directories": sorted(directories, key=lambda item: item.relative_to(artifact).as_posix()),
        "files_count": len(files), "directories_count": len(directories),
        "bytes": total, "artifact_sha256": aggregate.hexdigest(),
    }


def _add_snapshot(archive, artifact, snapshot):
    for directory in snapshot["directories"]:
        info = archive.gettarinfo(str(directory), arcname=directory.relative_to(artifact).as_posix())
        if not info.isdir():
            raise OSError(f"Artifact directory changed while archiving: {directory}")
        archive.addfile(info)
    for entry in snapshot["files"]:
        info = archive.gettarinfo(str(entry["path"]), arcname=entry["relative"])
        if not info.isfile():
            raise OSError(f"Artifact file changed while archiving: {entry['path']}")
        with entry["path"].open("rb") as source:
            archive.addfile(info, source)


def create_local_archive(command, artifact, snapshot):
    temporary = tempfile.NamedTemporaryFile(prefix="qzx-deploy-", suffix=".tar.gz", delete=False)
    archive_path = Path(temporary.name)
    temporary.close()
    try:
        with tarfile.open(archive_path, "w:gz") as archive:
            _add_snapshot(archive, artifact, snapshot)
            manifest = "".join(f"{entry['sha256']}  {entry['relative']}\n" for entry in snapshot["files"]).encode("utf-8")
            info = tarfile.TarInfo(command._manifest_name)
            info.size, info.mode, info.mtime = len(manifest), 0o600, 0
            archive.addfile(info, io.BytesIO(manifest))
        return archive_path
    except Exception:
        try:
            archive_path.unlink()
        except OSError:
            pass
        raise


def new_deployment_id():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{secrets.token_hex(4)}"


def remote_paths(target_path, deployment_id):
    return {
        "active": target_path, "stage": f"{target_path}.qzx-stage-{deployment_id}",
        "previous": f"{target_path}.qzx-previous-{deployment_id}",
        "failed": f"{target_path}.qzx-failed-{deployment_id}",
        "backup_archive": f"{target_path}.qzx-backup-{deployment_id}.tar.gz",
        "absence_marker": f"{target_path}.qzx-backup-{deployment_id}.absent",
        "lock": f"{target_path}.qzx-deploy-lock", "deployment_id": deployment_id,
    }

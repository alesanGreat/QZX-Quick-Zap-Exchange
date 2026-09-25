"""Manifest selection and version updates for ``prepareRelease``."""

import json
import os
import re

from packaging.version import InvalidVersion, Version


def select_manifest(command, project_path, requested_manifest):
    if requested_manifest not in (None, ""):
        candidate = (project_path / os.fspath(requested_manifest)).resolve()
        try:
            candidate.relative_to(project_path.resolve())
        except ValueError:
            return command._failure("manifest_outside_project", "The selected manifest must remain inside the project.", path=str(project_path), manifest=str(candidate))
        manifest_type = command.supported_manifests.get(candidate.name)
        if manifest_type is None:
            return command._failure("unsupported_manifest", f"Unsupported manifest '{candidate.name}'. Choose package.json, pyproject.toml, or Cargo.toml.", path=str(project_path), manifest=str(candidate))
        if not candidate.is_file() or candidate.is_symlink():
            return command._failure("manifest_not_regular_file", "The selected manifest must be an existing regular file.", path=str(project_path), manifest=str(candidate))
        return {"success": True, "path": candidate, "manifest_type": manifest_type}
    candidates = [
        (project_path / name, kind)
        for name, kind in command.supported_manifests.items()
        if (project_path / name).is_file() and not (project_path / name).is_symlink()
    ]
    if not candidates:
        return command._failure("manifest_not_found", "No supported release manifest was found. Add or select package.json, pyproject.toml, or Cargo.toml.", path=str(project_path))
    if len(candidates) > 1:
        return command._failure("ambiguous_manifest", "Multiple supported manifests were found. Select one explicitly with --manifest.", path=str(project_path), manifests=[str(item[0]) for item in candidates])
    path, kind = candidates[0]
    return {"success": True, "path": path, "manifest_type": kind}


def _npm_update(command, source, requested_version, bump):
    document = json.loads(source)
    old_version = document.get("version")
    if not isinstance(old_version, str) or not old_version.strip():
        raise ValueError("package.json has no top-level string version")
    target = command._target_version(old_version, requested_version, bump, "npm")
    document["version"] = target
    newline = "\r\n" if "\r\n" in source else "\n"
    content = json.dumps(document, ensure_ascii=False, indent=2).replace("\n", newline)
    if source.endswith(("\n", "\r\n")):
        content += newline
    return old_version, target, content


def _toml_update(command, source, manifest_path, manifest_type, requested_version, bump):
    section = "project" if manifest_type == "python" else "package"
    section_match = re.search(rf"(?ms)^\[{re.escape(section)}\]\s*$.*?(?=^\[|\Z)", source)
    if section_match is None:
        raise ValueError(f"{manifest_path.name} has no [{section}] section")
    version_match = re.search(r"(?m)^(\s*version\s*=\s*)([\"'])([^\"']+)\2(\s*(?:#.*)?)$", section_match.group(0))
    if version_match is None:
        raise ValueError(f"[{section}] has no static version assignment")
    old_version = version_match.group(3)
    target = command._target_version(old_version, requested_version, bump, manifest_type)
    start = section_match.start() + version_match.start(3)
    end = section_match.start() + version_match.end(3)
    return old_version, target, source[:start] + target + source[end:]


def manifest_update(command, manifest_path, manifest_type, bump, requested_version):
    try:
        original = manifest_path.read_bytes()
        prefix = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
        source = original[len(prefix) :].decode("utf-8")
        if manifest_type == "npm":
            old_version, target, content = _npm_update(command, source, requested_version, bump)
        else:
            old_version, target, content = _toml_update(command, source, manifest_path, manifest_type, requested_version, bump)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return command._failure("invalid_manifest", f"Could not read a static version from '{manifest_path}': {exc}", manifest=str(manifest_path), manifest_type=manifest_type)
    return {
        "success": True, "old_version": old_version, "new_version": target,
        "content": content, "content_bytes": prefix + content.encode("utf-8"),
    }


def target_version(command, old_version, requested_version, bump, manifest_type):
    if manifest_type == "python":
        try:
            current = Version(old_version)
        except InvalidVersion as exc:
            raise ValueError(f"current version is not valid PEP 440: {old_version!r}") from exc
        if requested_version not in (None, ""):
            try:
                target = Version(str(requested_version).strip())
            except InvalidVersion as exc:
                raise ValueError(f"target version is not valid PEP 440: {requested_version!r}") from exc
            if target <= current:
                raise ValueError(f"target version {target} must be newer than {current}")
            return str(target)
        return command._bump_python_version(current, bump)
    current_parts = command._semver_parts(old_version)
    if requested_version not in (None, ""):
        target_text = str(requested_version).strip()
        target_parts = command._semver_parts(target_text)
        if command._semver_key(target_parts) <= command._semver_key(current_parts):
            raise ValueError(f"target version {target_text} must be newer than {old_version}")
        return target_text
    return command._bump_semver(old_version, bump)


def bump_python_version(version, bump):
    release = list(version.release)
    while len(release) < 3:
        release.append(0)
    if bump == "major":
        release = [release[0] + 1, 0, 0]
    elif bump == "minor":
        release = [release[0], release[1] + 1, 0]
    else:
        release[-1] += 1
    return ".".join(str(part) for part in release)


def bump_semver(cls, version_str, bump):
    major, minor, patch, _suffix = cls._semver_parts(version_str)
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def semver_parts(version):
    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?", str(version).strip())
    if match is None:
        raise ValueError(f"version is not valid SemVer: {version!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), match.group(4)


def semver_key(parts):
    major, minor, patch, prerelease = parts
    return major, minor, patch, 1 if prerelease is None else 0, prerelease or ""

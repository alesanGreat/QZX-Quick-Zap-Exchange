"""Semantic validation for Golden Core release-quality attestations."""

from __future__ import annotations

import re
import subprocess

from qzx.core.command_loader import CommandLoader
from qzx.core.implementation_digest import command_implementation_digest


_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_REQUIRED_QUALITY_GATES = (
    "exact_release_tag_verified",
    "distribution_artifacts_verified",
    "twine_check_passed",
    "pypi_artifacts_verified",
    "github_release_assets_verified",
    "ci_matrix_passed",
    "digest_bound_platform_evidence_verified",
    "result_contract_verified",
    "zero_known_release_blockers",
)


def validate_release_quality(
    document,
    registry,
    *,
    attested_command_names,
    canonical_sha256,
    verify_git,
    verify_current_implementations,
    project_root,
):
    """Return ordered validation errors for one release-quality attestation."""
    errors = []
    try:
        names = attested_command_names(document)
    except ValueError as exception:
        names = []
        errors.append(str(exception))

    policy = registry.get("release_quality_policy")
    if not isinstance(policy, dict):
        return ["Golden Core release_quality_policy is missing."]

    policy_errors, blocking_label = _policy_errors(policy)
    errors.extend(policy_errors)
    errors.extend(_attestation_metadata_errors(document))

    release, release_context, release_errors = _release_context(document)
    errors.extend(release_errors)
    errors.extend(_distribution_errors(release))
    errors.extend(_artifact_errors(release, release_context["version"]))
    errors.extend(_ci_errors(document, names, release_context["source_revision"]))

    commands, command_errors = _command_map_errors(document, names)
    errors.extend(command_errors)
    if verify_current_implementations:
        errors.extend(_current_implementation_errors(commands, names))

    errors.extend(_quality_gate_errors(document, blocking_label))
    errors.extend(_attestation_hash_errors(document, canonical_sha256))
    if verify_git:
        errors.extend(
            _git_tag_errors(
                release_context["tag"],
                release_context["source_revision"],
                project_root,
            )
        )
    return errors


def _policy_errors(policy):
    errors = []
    for flag in (
        "requires_exact_release_tag",
        "requires_verified_distribution_hashes",
        "requires_successful_ci",
        "requires_digest_bound_platform_evidence",
        "requires_zero_known_release_blockers",
    ):
        if policy.get(flag) is not True:
            errors.append(
                f"Golden Core release-quality policy must enable {flag}."
            )
    blocking_label = policy.get("blocking_issue_label")
    if not _nonempty_text(blocking_label):
        errors.append(
            "Golden Core release-quality policy needs a blocking issue label."
        )
    return errors, blocking_label


def _attestation_metadata_errors(document):
    errors = []
    if document.get("schema_version") != 1:
        errors.append(
            "Release-quality attestation must use schema_version 1."
        )
    if document.get("evidence_type") != "qzx_golden_core_release_quality":
        errors.append(
            "Release-quality attestation has an unexpected evidence_type."
        )
    if document.get("status") != "verified":
        errors.append(
            "Release-quality attestation status must be verified."
        )
    if not _nonempty_text(document.get("evidence_scope")):
        errors.append(
            "Release-quality evidence_scope must be non-empty text."
        )
    limitations = document.get("limitations")
    if (
        not isinstance(limitations, list)
        or len(limitations) < 2
        or not all(_nonempty_text(item) for item in limitations)
    ):
        errors.append(
            "Release-quality attestation must disclose at least two limitations."
        )
    return errors


def _release_context(document):
    errors = []
    release = document.get("release")
    if not isinstance(release, dict):
        errors.append(
            "Release-quality attestation has no release object."
        )
        release = {}
    version = release.get("version")
    tag = release.get("tag")
    source_revision = release.get("source_revision")
    if not _nonempty_text(version):
        errors.append("Release-quality version must be non-empty text.")
    if not isinstance(tag, str) or tag != f"v{version}":
        errors.append("Release-quality tag must be v<version>.")
    if (
        not isinstance(source_revision, str)
        or _COMMIT_PATTERN.fullmatch(source_revision) is None
    ):
        errors.append(
            "Release-quality source_revision must be a 40-character Git SHA."
        )
    if release.get("status") != "Alpha":
        errors.append(
            "Golden Core release-quality evidence currently expects an Alpha release."
        )
    if not _nonempty_text(release.get("released_at")):
        errors.append(
            "Release-quality released_at must be non-empty text."
        )
    return release, {
        "version": version,
        "tag": tag,
        "source_revision": source_revision,
    }, errors


def _distribution_errors(release):
    errors = []
    pypi = release.get("pypi")
    github = release.get("github")
    if not isinstance(pypi, dict):
        errors.append(
            "Release-quality attestation has no PyPI evidence."
        )
        pypi = {}
    if not isinstance(github, dict):
        errors.append(
            "Release-quality attestation has no GitHub Release evidence."
        )
        github = {}
    if pypi.get("published") is not True:
        errors.append(
            "PyPI evidence must confirm the exact release is published."
        )
    if pypi.get("requires_python") != ">=3.13":
        errors.append(
            "PyPI evidence must confirm requires_python >=3.13."
        )
    if github.get("prerelease") is not True or github.get("draft") is not False:
        errors.append(
            "GitHub evidence must describe a published pre-release, not a draft."
        )
    if (
        not isinstance(github.get("asset_count"), int)
        or github.get("asset_count", 0) < 3
    ):
        errors.append(
            "GitHub Release must expose at least wheel, sdist, and platform summary."
        )
    return errors


def _artifact_errors(release, version):
    artifacts = release.get("artifacts")
    if not isinstance(artifacts, dict):
        return ["Release-quality attestation has no artifact map."]
    errors = []
    expected = {
        "wheel": f"qzx-{version}-py3-none-any.whl",
        "sdist": f"qzx-{version}.tar.gz",
    }
    for kind, filename in expected.items():
        artifact = artifacts.get(kind)
        if not isinstance(artifact, dict):
            errors.append(
                f"Release-quality attestation is missing {kind} evidence."
            )
            continue
        if artifact.get("filename") != filename:
            errors.append(
                f"Release-quality {kind} filename does not match the release version."
            )
        if not _valid_sha256(artifact.get("sha256")):
            errors.append(
                f"Release-quality {kind} SHA-256 is invalid."
            )
    return errors


def _ci_errors(document, names, source_revision):
    ci = document.get("ci")
    errors = []
    if not isinstance(ci, dict):
        errors.append("Release-quality attestation has no CI evidence.")
        ci = {}
    if ci.get("conclusion") != "success":
        errors.append("Release-quality CI conclusion must be success.")
    if ci.get("source_revision") != source_revision:
        errors.append(
            "Release-quality CI source revision differs from the release tag revision."
        )
    run_id = ci.get("run_id")
    if not isinstance(run_id, int) or run_id <= 0:
        errors.append(
            "Release-quality CI run_id must be a positive integer."
        )
    errors.extend(_ci_run_count_errors(ci, names))
    for field in (
        "platform_aggregate_sha256",
        "platform_summary_file_sha256",
    ):
        if not _valid_sha256(ci.get(field)):
            errors.append(f"Release-quality CI {field} is invalid.")
    return errors


def _ci_run_count_errors(ci, names):
    errors = []
    environment_count = ci.get("environment_count")
    command_runs = ci.get("command_environment_runs")
    if not isinstance(environment_count, int) or environment_count < 3:
        errors.append(
            "Release-quality CI must cover at least three environments."
        )
    if (
        isinstance(environment_count, int)
        and command_runs != len(names) * environment_count
    ):
        errors.append(
            "Release-quality CI command/environment run count is inconsistent."
        )
    if ci.get("failed_command_runs") != 0:
        errors.append(
            "Release-quality CI must report zero failed Golden Core command runs."
        )
    return errors


def _command_map_errors(document, names):
    commands = document.get("commands")
    errors = []
    if not isinstance(commands, dict) or set(commands) != set(names):
        errors.append("Release-quality command map is malformed.")
        commands = {}
    for name in names:
        record = commands.get(name)
        if not isinstance(record, dict):
            errors.append(
                f"Release-quality command record is missing: {name}."
            )
            continue
        if not _valid_sha256(record.get("implementation_digest")):
            errors.append(
                f"Release-quality implementation digest is invalid for {name}."
            )
        if record.get("release_blockers") != []:
            errors.append(
                f"Release-quality command has unresolved blockers: {name}."
            )
    return commands, errors


def _current_implementation_errors(commands, names):
    errors = []
    loader = CommandLoader()
    for name in names:
        command = loader.get_command(name)
        if command is None:
            errors.append(
                f"Attested command is no longer a current canonical command: {name}."
            )
            continue
        record = commands.get(name)
        if not isinstance(record, dict):
            continue
        digest = command_implementation_digest(type(command))
        if record.get("implementation_digest") != digest:
            errors.append(
                f"Release-quality implementation digest is stale for current {name}."
            )
    return errors


def _quality_gate_errors(document, blocking_label):
    gates = document.get("quality_gates")
    errors = []
    if not isinstance(gates, dict):
        errors.append(
            "Release-quality quality_gates must be an object."
        )
        gates = {}
    for gate in _REQUIRED_QUALITY_GATES:
        if gates.get(gate) is not True:
            errors.append(
                f"Release-quality gate is not verified: {gate}."
            )
    if gates.get("blocking_issue_label") != blocking_label:
        errors.append(
            "Release-quality blocking issue label differs from Golden Core policy."
        )
    if gates.get("known_release_blockers") != []:
        errors.append(
            "Release-quality attestation must contain zero known release blockers."
        )
    errors.extend(_nonblocking_work_errors(gates.get("open_nonblocking_work")))
    return errors


def _nonblocking_work_errors(nonblocking):
    if not isinstance(nonblocking, list):
        return [
            "Release-quality open_nonblocking_work must be an array."
        ]
    for item in nonblocking:
        if not isinstance(item, dict) or item.get("blocking") is not False:
            return [
                "Release-quality nonblocking work must be explicit non-blocking records."
            ]
    return []


def _attestation_hash_errors(document, canonical_sha256):
    observed = document.get("attestation_sha256")
    payload = dict(document)
    payload.pop("attestation_sha256", None)
    if observed == canonical_sha256(payload):
        return []
    return ["Release-quality attestation SHA-256 is invalid."]


def _git_tag_errors(tag, source_revision, project_root):
    if not isinstance(tag, str) or not isinstance(source_revision, str):
        return []
    completed = subprocess.run(
        ["git", "rev-list", "-n", "1", tag],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        return [f"Git could not resolve release-quality tag {tag}."]
    if completed.stdout.strip() != source_revision:
        return [
            "Release-quality tag does not resolve to source_revision."
        ]
    return []


def _valid_sha256(value):
    return (
        isinstance(value, str)
        and _SHA256_PATTERN.fullmatch(value) is not None
    )


def _nonempty_text(value):
    return isinstance(value, str) and bool(value.strip())

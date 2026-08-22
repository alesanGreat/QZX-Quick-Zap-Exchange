"""Deterministic tests for the GitHub/PyPI/website parity gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "verify_public_surface_parity.py"
WORKFLOW_PATH = (
    REPOSITORY_ROOT / ".github" / "workflows" / "public-surface-parity.yml"
)
VERSION = "0.2.2.0.7a6"
COMMIT = "1" * 40
WHEEL = f"qzx-{VERSION}-py3-none-any.whl"
SDIST = f"qzx-{VERSION}.tar.gz"
WHEEL_DIGEST = "a" * 64
SDIST_DIGEST = "b" * 64
COMMANDS = ["about", "countLines"]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "qzx_verify_public_surface_parity",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest():
    return {
        "channels": {
            "published": {
                "version": VERSION,
                "wheel": {
                    "filename": WHEEL,
                    "command_names": list(COMMANDS),
                },
            },
            "development": {"version": VERSION},
        }
    }


def _command_index():
    return [{"name": name} for name in COMMANDS]


def _responses(*, website_commit=COMMIT, wheel_digest=WHEEL_DIGEST):
    return {
        "commits/main": {"sha": COMMIT},
        f"releases/tags/v{VERSION}": {
            "tag_name": f"v{VERSION}",
            "draft": False,
            "prerelease": True,
            "assets": [
                {
                    "name": WHEEL,
                    "digest": f"sha256:{wheel_digest}",
                    "browser_download_url": "https://download.invalid/wheel",
                },
                {
                    "name": SDIST,
                    "digest": f"sha256:{SDIST_DIGEST}",
                    "browser_download_url": "https://download.invalid/sdist",
                },
            ],
        },
        f"git/ref/tags/v{VERSION}": {
            "object": {"type": "commit", "sha": COMMIT}
        },
        "pypi": {
            "info": {"version": VERSION},
            "urls": [
                {
                    "filename": WHEEL,
                    "digests": {"sha256": WHEEL_DIGEST},
                },
                {
                    "filename": SDIST,
                    "digests": {"sha256": SDIST_DIGEST},
                },
            ],
        },
        "website": {
            "metadata": {
                "development_version": VERSION,
                "published_version": VERSION,
                "documentation_commit": website_commit,
                "documentation_branch": "main",
                "documented_command_count": len(COMMANDS),
            },
            "commands": {name: {} for name in COMMANDS},
        },
    }


def _fetcher(responses):
    def get_json(url):
        if "pypi.org" in url:
            return responses["pypi"]
        if "qzx.yumbale.com" in url:
            return responses["website"]
        for suffix, payload in responses.items():
            if suffix in {"pypi", "website"}:
                continue
            if url.endswith(suffix):
                return payload
        raise AssertionError(f"Unexpected URL: {url}")

    return get_json


def test_all_public_surfaces_must_match_version_commit_inventory_and_bytes():
    parity = _load_module()
    responses = _responses()

    result = parity.verify_public_surface_parity(
        manifest=_manifest(),
        command_index=_command_index(),
        expected_version=VERSION,
        expected_commit=COMMIT,
        get_json=_fetcher(responses),
        get_bytes=lambda _url: b"must not download when digest metadata exists",
    )

    assert result["success"] is True
    assert result["mismatches"] == []
    assert result["expected"]["artifacts"] == [WHEEL, SDIST]


def test_stale_website_commit_and_artifact_divergence_block_completion():
    parity = _load_module()
    responses = _responses(
        website_commit="2" * 40,
        wheel_digest="c" * 64,
    )

    result = parity.verify_public_surface_parity(
        manifest=_manifest(),
        command_index=_command_index(),
        expected_version=VERSION,
        expected_commit=COMMIT,
        get_json=_fetcher(responses),
        get_bytes=lambda _url: b"unused",
    )

    assert result["success"] is False
    mismatches = {
        (item["surface"], item["check"])
        for item in result["mismatches"]
    }
    assert ("website", "documentation_commit") in mismatches
    assert ("artifact_parity", WHEEL) in mismatches


def test_annotated_release_tag_is_dereferenced_to_its_commit():
    parity = _load_module()
    responses = _responses()
    responses[f"git/ref/tags/v{VERSION}"] = {
        "object": {"type": "tag", "sha": "3" * 40}
    }
    responses[f"git/tags/{'3' * 40}"] = {
        "object": {"type": "commit", "sha": COMMIT}
    }

    result = parity.verify_public_surface_parity(
        manifest=_manifest(),
        command_index=_command_index(),
        expected_version=VERSION,
        expected_commit=COMMIT,
        get_json=_fetcher(responses),
        get_bytes=lambda _url: b"unused",
    )

    assert result["success"] is True


def test_scheduled_and_main_push_workflow_runs_the_parity_gate():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "branches:\n      - main" in workflow
    assert "scripts/verify_public_surface_parity.py" in workflow
    assert '--expected-commit "$GITHUB_SHA"' in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "persist-credentials: false" in workflow


def test_pre_main_mode_checks_every_other_surface_without_fetching_main():
    parity = _load_module()
    responses = _responses()
    responses.pop("commits/main")

    result = parity.verify_public_surface_parity(
        manifest=_manifest(),
        command_index=_command_index(),
        expected_version=VERSION,
        expected_commit=COMMIT,
        get_json=_fetcher(responses),
        get_bytes=lambda _url: b"unused",
        require_main=False,
    )

    assert result["success"] is True
    assert all(check["surface"] != "github_main" for check in result["checks"])

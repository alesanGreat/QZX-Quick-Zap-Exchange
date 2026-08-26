"""Deterministic tests for the local/GitHub/PyPI/website parity gate."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import zipfile

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "verify_public_surface_parity.py"
WORKFLOW_PATH = (
    REPOSITORY_ROOT / ".github" / "workflows" / "public-surface-parity.yml"
)
VERSION = "0.2.2.0.7a7"
COMMIT = "1" * 40
WHEEL = f"qzx-{VERSION}-py3-none-any.whl"
SDIST = f"qzx-{VERSION}.tar.gz"
COMMANDS = ["about", "countLines"]
ONBOARDING = {
    "schema_version": 1,
    "default_risk": "read_only",
    "documentation_url_key": "command_catalog",
    "security_url_key": "security",
    "steps": [
        {
            "stage": "first_success",
            "command": "about",
            "arguments": [],
            "machine_output": True,
            "purpose": {
                "en": "Confirm QZX with one read-only result.",
                "es": "Confirma QZX con un resultado de solo lectura.",
            },
        },
        {
            "stage": "explore",
            "command": "countLines",
            "arguments": ["README.md"],
            "machine_output": False,
            "purpose": {
                "en": "Explore one installed command.",
                "es": "Explora un comando instalado.",
            },
        },
        {
            "stage": "understand",
            "command": "about",
            "arguments": [],
            "machine_output": False,
            "purpose": {
                "en": "Understand the product before execution.",
                "es": "Comprende el producto antes de ejecutar.",
            },
        },
    ],
}


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


def _manifest(*, commands=None, onboarding=None):
    command_names = list(COMMANDS if commands is None else commands)
    onboarding_contract = json.loads(
        json.dumps(ONBOARDING if onboarding is None else onboarding)
    )
    return {
        "urls": {
            "command_catalog": "https://qzx.yumbale.com/en/commands",
            "security": "https://qzx.yumbale.com/en/security",
        },
        "onboarding": onboarding_contract,
        "channels": {
            "published": {
                "version": VERSION,
                "requires_python": ">=3.13",
                "wheel": {
                    "filename": WHEEL,
                    "command_names": command_names,
                },
            },
            "development": {"version": VERSION},
        }
    }


def _command_index(*, commands=None):
    command_names = list(COMMANDS if commands is None else commands)
    return {
        "schema_version": 2,
        "commands": [{"name": name} for name in command_names],
    }


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")


def _artifact_bytes(filename, *, manifest=None, command_index=None):
    manifest = _manifest() if manifest is None else manifest
    command_index = _command_index() if command_index is None else command_index
    members = {
        "src/qzx/resources/command-index.json": _json_bytes(command_index),
        "src/qzx/resources/product-manifest.json": _json_bytes(manifest),
    }
    buffer = io.BytesIO()
    if filename.endswith(".whl"):
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path, payload in members.items():
                archive.writestr(path.removeprefix("src/"), payload)
    else:
        root = f"qzx-{VERSION}"
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            for path, payload in members.items():
                info = tarfile.TarInfo(f"{root}/{path}")
                info.size = len(payload)
                info.mtime = 0
                archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _responses(
    *,
    website_commit=COMMIT,
    github_wheel=None,
    artifact_manifest=None,
):
    pypi_payloads = {
        WHEEL: _artifact_bytes(WHEEL, manifest=artifact_manifest),
        SDIST: _artifact_bytes(SDIST, manifest=artifact_manifest),
    }
    github_payloads = dict(pypi_payloads)
    if github_wheel is not None:
        github_payloads[WHEEL] = github_wheel

    github_urls = {
        filename: f"https://download.invalid/github/{filename}"
        for filename in (WHEEL, SDIST)
    }
    pypi_urls = {
        filename: f"https://download.invalid/pypi/{filename}"
        for filename in (WHEEL, SDIST)
    }
    downloads = {
        **{github_urls[name]: payload for name, payload in github_payloads.items()},
        **{pypi_urls[name]: payload for name, payload in pypi_payloads.items()},
    }
    return {
        "commits/main": {"sha": COMMIT},
        f"releases/tags/v{VERSION}": {
            "tag_name": f"v{VERSION}",
            "draft": False,
            "prerelease": True,
            "assets": [
                {
                    "name": filename,
                    "digest": (
                        "sha256:" + hashlib.sha256(github_payloads[filename]).hexdigest()
                    ),
                    "browser_download_url": github_urls[filename],
                }
                for filename in (WHEEL, SDIST)
            ],
        },
        f"git/ref/tags/v{VERSION}": {
            "object": {"type": "commit", "sha": COMMIT}
        },
        "pypi": {
            "info": {
                "version": VERSION,
                "requires_python": ">=3.13",
            },
            "urls": [
                {
                    "filename": filename,
                    "url": pypi_urls[filename],
                    "digests": {
                        "sha256": hashlib.sha256(pypi_payloads[filename]).hexdigest()
                    },
                }
                for filename in (WHEEL, SDIST)
            ],
        },
        "website": {
            "metadata": {
                "development_version": VERSION,
                "published_version": VERSION,
                "documentation_commit": website_commit,
                "documentation_branch": "main",
                "documented_command_count": len(COMMANDS),
                "published_wheel_entry_count": len(COMMANDS),
                "published_capability_count": len(COMMANDS),
                "retired_published_entry_count": 0,
                "retired_published_names": [],
                "development_only_count": 0,
                "published_name_to_canonical": {
                    name: name for name in COMMANDS
                },
                "onboarding": json.loads(json.dumps(ONBOARDING)),
            },
            "commands": {name: {} for name in COMMANDS},
        },
        "downloads": downloads,
    }


def _json_fetcher(responses):
    def get_json(url):
        if "pypi.org" in url:
            return responses["pypi"]
        if "qzx.yumbale.com" in url:
            return responses["website"]
        for suffix, payload in responses.items():
            if suffix in {"pypi", "website", "downloads"}:
                continue
            if url.endswith(suffix):
                return payload
        raise AssertionError(f"Unexpected URL: {url}")

    return get_json


def _bytes_fetcher(responses):
    def get_bytes(url):
        try:
            return responses["downloads"][url]
        except KeyError as error:
            raise AssertionError(f"Unexpected download URL: {url}") from error

    return get_bytes


def _verify(parity, responses, **overrides):
    arguments = {
        "manifest": _manifest(),
        "command_index": _command_index(),
        "expected_version": VERSION,
        "expected_commit": COMMIT,
        "get_json": _json_fetcher(responses),
        "get_bytes": _bytes_fetcher(responses),
    }
    arguments.update(overrides)
    return parity.verify_public_surface_parity(**arguments)


def test_all_public_surfaces_match_version_commit_inventory_and_bytes():
    parity = _load_module()
    responses = _responses()

    result = _verify(parity, responses)

    assert result["success"] is True
    assert result["mismatches"] == []
    assert result["expected"]["artifacts"] == [WHEEL, SDIST]
    assert result["expected"]["command_names"] == COMMANDS
    assert result["expected"]["onboarding"] == ONBOARDING


def test_stale_website_commit_and_artifact_divergence_block_completion():
    parity = _load_module()
    responses = _responses(
        website_commit="2" * 40,
        github_wheel=b"different immutable wheel bytes",
    )

    result = _verify(parity, responses)

    assert result["success"] is False
    mismatches = {
        (item["surface"], item["check"])
        for item in result["mismatches"]
    }
    assert ("website", "documentation_commit") in mismatches
    assert ("artifact_parity", WHEEL) in mismatches


def test_website_onboarding_cannot_drift_from_the_packaged_contract():
    parity = _load_module()
    responses = _responses()
    responses["website"]["metadata"]["onboarding"]["steps"][0]["purpose"][
        "en"
    ] = "Stale website copy."

    result = _verify(parity, responses)

    assert result["success"] is False
    mismatches = {
        (item["surface"], item["check"])
        for item in result["mismatches"]
    }
    assert ("website", "onboarding") in mismatches


def test_distribution_manifest_cannot_disagree_with_onboarding_source():
    parity = _load_module()
    artifact_manifest = _manifest()
    artifact_manifest["onboarding"]["steps"][0]["command"] = "countLines"
    responses = _responses(artifact_manifest=artifact_manifest)

    result = _verify(parity, responses)

    assert result["success"] is False
    mismatches = {
        (item["surface"], item["check"])
        for item in result["mismatches"]
    }
    assert ("pypi_wheel", "internal_product_manifest") in mismatches
    assert ("pypi_wheel", "internal_onboarding") in mismatches
    assert ("pypi_sdist", "internal_product_manifest") in mismatches
    assert ("pypi_sdist", "internal_onboarding") in mismatches


def test_distribution_manifest_cannot_disagree_with_installed_commands():
    parity = _load_module()
    artifact_manifest = _manifest(commands=["about", "oldCountLines"])
    responses = _responses(artifact_manifest=artifact_manifest)

    result = _verify(parity, responses)

    assert result["success"] is False
    mismatches = {
        (item["surface"], item["check"])
        for item in result["mismatches"]
    }
    assert ("pypi_wheel", "internal_product_manifest") in mismatches
    assert ("pypi_wheel", "internal_manifest_command_inventory") in mismatches
    assert ("pypi_sdist", "internal_product_manifest") in mismatches
    assert ("pypi_sdist", "internal_manifest_command_inventory") in mismatches


def test_schema_v2_command_index_is_used_without_compatibility_rewriting():
    parity = _load_module()
    responses = _responses()

    result = _verify(parity, responses, command_index=_command_index())

    assert result["success"] is True
    with pytest.raises(ValueError, match="one JSON object"):
        _verify(
            parity,
            responses,
            command_index=[{"name": name} for name in COMMANDS],
        )


@pytest.mark.parametrize("token_name", ("GH_TOKEN", "GITHUB_TOKEN"))
def test_github_token_is_never_sent_to_pypi_site_or_asset_hosts(
    monkeypatch,
    token_name,
):
    parity = _load_module()
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv(token_name, "top-secret-token")

    api_headers = parity._request_headers("https://api.github.com/repos/example")
    assert api_headers["Authorization"] == "Bearer top-secret-token"
    for url in (
        "https://pypi.org/pypi/qzx/json",
        "https://qzx.yumbale.com/data/commands.json",
        "https://github.com/example/releases/download/file.whl",
        "https://release-assets.githubusercontent.com/file.whl",
    ):
        assert "Authorization" not in parity._request_headers(url)


def test_annotated_release_tag_is_dereferenced_to_its_commit():
    parity = _load_module()
    responses = _responses()
    responses[f"git/ref/tags/v{VERSION}"] = {
        "object": {"type": "tag", "sha": "3" * 40}
    }
    responses[f"git/tags/{'3' * 40}"] = {
        "object": {"type": "commit", "sha": COMMIT}
    }

    result = _verify(parity, responses)

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

    result = _verify(parity, responses, require_main=False)

    assert result["success"] is True
    assert all(
        check["surface"] != "github_main" for check in result["checks"]
    )

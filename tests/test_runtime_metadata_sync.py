"""Regression tests for release-bound README metadata projection."""

from __future__ import annotations

from copy import deepcopy

import pytest

from scripts import sync_runtime_metadata as metadata_sync


def test_stable_channel_projection_is_complete_and_uses_live_command_count():
    manifest = deepcopy(metadata_sync.load_manifest())
    published = manifest["channels"]["published"]
    published["version"] = "9.8.7"
    published["install_command"] = "python -m pip install --upgrade qzx"

    rendered = metadata_sync.synchronized_readme_content(manifest)
    command_count = metadata_sync._canonical_command_count()

    assert rendered.count("python -m pip install --upgrade qzx") == 2
    assert "pipx install qzx" in rendered
    assert "pipx run --spec qzx qzx version" in rendered
    assert 'python -m pip install --upgrade "qzx[filetype]"' in rendered
    assert 'python -m pip install --upgrade "qzx[ai]"' in rendered
    assert "uses pip's normal installation channel" in rendered
    assert f"{command_count} canonical commands in the generated command index" in rendered


def test_prerelease_projection_updates_every_install_surface():
    manifest = deepcopy(metadata_sync.load_manifest())
    published = manifest["channels"]["published"]
    published["version"] = "9.8.7a1"
    published["install_command"] = "python -m pip install --pre --upgrade qzx"

    rendered = metadata_sync.synchronized_readme_content(manifest)

    assert rendered.count("python -m pip install --pre --upgrade qzx") == 2
    assert "pipx install --pip-args='--pre' qzx" in rendered
    assert "pipx run --pip-args='--pre' --spec qzx qzx version" in rendered
    assert 'python -m pip install --pre --upgrade "qzx[filetype]"' in rendered
    assert 'python -m pip install --pre --upgrade "qzx[ai]"' in rendered
    assert "selects the latest final release; use" in rendered
    assert "`--pre` to opt into this Alpha pre-release" in rendered
    assert "This source release is QZX `9.8.7a1`" in rendered


def test_release_projection_rejects_unknown_install_channel():
    manifest = deepcopy(metadata_sync.load_manifest())
    manifest["channels"]["published"]["install_command"] = "pip install qzx"

    with pytest.raises(ValueError, match="supported QZX channel command"):
        metadata_sync.synchronized_readme_content(manifest)


def test_validated_onboarding_preserves_packaged_contract():
    manifest = deepcopy(metadata_sync.load_manifest())

    onboarding = metadata_sync.validated_onboarding(manifest)

    assert onboarding == manifest["onboarding"]
    assert onboarding is not manifest["onboarding"]
    assert [step["stage"] for step in onboarding["steps"]] == [
        "first_success",
        "explore",
        "understand",
    ]


def test_generated_content_projects_runtime_constants():
    manifest = deepcopy(metadata_sync.load_manifest())

    rendered = metadata_sync.generated_content(manifest)
    namespace = {}
    exec(rendered, namespace)

    assert namespace["VERSION"] == manifest["channels"]["development"]["version"]
    assert namespace["ATTRIBUTION"] == manifest["product"]["attribution"]
    assert namespace["ONBOARDING"] == manifest["onboarding"]
    assert namespace["COMMAND_CATALOG_URL"].startswith("https://")
    assert namespace["SECURITY_GUIDE_URL"].startswith("https://")
    assert namespace["WELCOME_MATURITY"]["stage"]

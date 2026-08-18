"""Regression coverage for README links rendered into PyPI metadata."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from scripts.verify_distribution_artifacts import (
    find_repository_relative_links,
    render_package_readme,
    verify_package_index_links,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
README_PATH = PROJECT_ROOT / "README.md"
MANIFEST_PATH = PROJECT_ROOT / "MANIFEST.in"
PRODUCT_MANIFEST_PATH = (
    PROJECT_ROOT / "src" / "qzx" / "resources" / "product-manifest.json"
)


def package_context() -> tuple[str, str]:
    manifest = json.loads(PRODUCT_MANIFEST_PATH.read_text(encoding="utf-8"))
    repository = manifest["urls"]["repository"]
    version = manifest["channels"]["development"]["version"]
    return repository, version


def test_current_readme_becomes_package_index_safe() -> None:
    source = README_PATH.read_text(encoding="utf-8")
    repository, version = package_context()
    source_relative = find_repository_relative_links(source)

    assert "CONTRIBUTING.md" in source_relative
    assert "docs/philosophy.md" in source_relative
    assert "LICENSE" in source_relative

    rendered = render_package_readme(
        source,
        repository_url=repository,
        revision=f"v{version}",
    )

    assert find_repository_relative_links(rendered) == []
    assert (
        f"{repository}/blob/v{version}/CONTRIBUTING.md"
        in rendered
    )
    assert (
        f"{repository}/blob/v{version}/docs/philosophy.md"
        in rendered
    )
    assert f"{repository}/blob/v{version}/LICENSE" in rendered
    verify_package_index_links(rendered, "rendered README")


def test_setup_long_description_uses_package_index_renderer() -> None:
    """Keep this integration check dependency-free in the runtime test matrix."""

    setup_path = PROJECT_ROOT / "setup.py"
    tree = ast.parse(setup_path.read_text(encoding="utf-8"), filename=str(setup_path))
    assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "long_description"
            for target in node.targets
        )
    ]

    assert len(assignments) == 1
    call = assignments[0].value
    assert isinstance(call, ast.Call)
    assert isinstance(call.func, ast.Attribute)
    assert isinstance(call.func.value, ast.Name)
    assert call.func.value.id == "distribution_helpers"
    assert call.func.attr == "render_package_readme"
    assert {keyword.arg for keyword in call.keywords} == {
        "repository_url",
        "revision",
    }


def test_readme_support_guide_is_available_in_source_distributions() -> None:
    source = README_PATH.read_text(encoding="utf-8")
    manifest_lines = {
        line.strip()
        for line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines()
    }

    assert ".github/SUPPORT.md" in find_repository_relative_links(source)
    assert "include .github/SUPPORT.md" in manifest_lines


def test_renderer_preserves_non_repository_links_and_fragments() -> None:
    markdown = (
        "[external](https://example.com/docs) "
        "[mail](mailto:team@example.com) "
        "[anchor](#section) "
        "[local](docs/guide.md?view=full#details)\n"
        "[license]: LICENSE\n"
    )

    rendered = render_package_readme(
        markdown,
        repository_url="https://github.com/example/project",
        revision="v1.2.3",
    )

    assert "(https://example.com/docs)" in rendered
    assert "(mailto:team@example.com)" in rendered
    assert "(#section)" in rendered
    assert (
        "(https://github.com/example/project/blob/v1.2.3/"
        "docs/guide.md?view=full#details)"
        in rendered
    )
    assert (
        "[license]: https://github.com/example/project/blob/v1.2.3/LICENSE"
        in rendered
    )


def test_renderer_rejects_links_that_escape_repository_root() -> None:
    with pytest.raises(ValueError, match="escapes the repository root"):
        render_package_readme(
            "[outside](../private.md)",
            repository_url="https://github.com/example/project",
            revision="v1.2.3",
        )


def test_distribution_verifier_rejects_relative_pypi_links() -> None:
    with pytest.raises(ValueError, match="PyPI cannot resolve"):
        verify_package_index_links(
            "See [contributing](CONTRIBUTING.md) and [license](LICENSE).",
            "wheel metadata",
        )

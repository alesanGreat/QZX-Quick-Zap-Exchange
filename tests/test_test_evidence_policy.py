"""Prevent test substitutions from masquerading as integration evidence."""

import ast
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parent


def _dotted_name(node):
    """Return a dotted call name such as ``pytest.mark.skipif``."""

    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def test_suite_does_not_runtime_patch_dependencies_or_skip_evidence():
    """Runtime patching and silent skips require redesign, not an exception."""

    violations = []
    this_file = Path(__file__).resolve()

    for test_file in sorted(TEST_ROOT.rglob("*.py")):
        if test_file.resolve() == this_file:
            continue
        tree = ast.parse(
            test_file.read_text(encoding="utf-8"),
            filename=str(test_file),
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (
                node.module == "unittest.mock"
                or node.module == "mock"
            ):
                violations.append(
                    f"{test_file}:{node.lineno}: runtime mock import"
                )
            elif isinstance(node, ast.Import):
                for imported in node.names:
                    if imported.name in {"unittest.mock", "mock"}:
                        violations.append(
                            f"{test_file}:{node.lineno}: runtime mock import"
                        )
            elif isinstance(node, ast.Call):
                called = node.func
                dotted_name = _dotted_name(called)
                if dotted_name == "monkeypatch.setattr":
                    violations.append(
                        f"{test_file}:{node.lineno}: monkeypatch.setattr"
                    )
                if dotted_name in {
                    "pytest.skip",
                    "pytest.skipif",
                    "pytest.xfail",
                    "pytest.mark.skip",
                    "pytest.mark.skipif",
                    "pytest.mark.xfail",
                    "unittest.skip",
                    "unittest.skipIf",
                    "unittest.skipUnless",
                    "unittest.expectedFailure",
                }:
                    violations.append(
                        f"{test_file}:{node.lineno}: silent skip/xfail"
                    )

    assert violations == [], (
        "Tests must use real boundaries or explicit injected deterministic "
        "fakes; runtime patching and silent skips cannot certify behavior:\n"
        + "\n".join(violations)
    )

"""Prevent test substitutions from masquerading as integration evidence."""

import ast
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parent


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
                if (
                    isinstance(called, ast.Attribute)
                    and called.attr == "setattr"
                    and isinstance(called.value, ast.Name)
                    and called.value.id == "monkeypatch"
                ):
                    violations.append(
                        f"{test_file}:{node.lineno}: monkeypatch.setattr"
                    )
                if (
                    isinstance(called, ast.Attribute)
                    and called.attr in {"skip", "skipif", "xfail"}
                    and isinstance(called.value, ast.Name)
                    and called.value.id in {"pytest", "unittest"}
                ):
                    violations.append(
                        f"{test_file}:{node.lineno}: silent skip/xfail"
                    )

    assert violations == [], (
        "Tests must use real boundaries or explicit injected deterministic "
        "fakes; runtime patching and silent skips cannot certify behavior:\n"
        + "\n".join(violations)
    )

"""Architecture boundaries shared by every public command module."""

import ast
from pathlib import Path


COMMAND_ROOT = (
    Path(__file__).resolve().parents[1] / "src" / "qzx" / "commands"
)


def _dotted_name(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def test_command_imports_do_not_mutate_python_module_resolution():
    violations = []

    for source in sorted(COMMAND_ROOT.rglob("*.py")):
        tree = ast.parse(
            source.read_text(encoding="utf-8"),
            filename=str(source),
        )
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and _dotted_name(node.func)
                in {"sys.path.append", "sys.path.insert", "sys.path.extend"}
            ):
                violations.append(
                    f"{source.relative_to(COMMAND_ROOT)}:{node.lineno}"
                )

    assert violations == [], (
        "Command modules must rely on the installed package or the caller's "
        "PYTHONPATH; import-time sys.path mutation makes resolution "
        "order-dependent:\n" + "\n".join(violations)
    )

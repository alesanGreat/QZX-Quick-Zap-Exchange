"""Static policy: QZX core and commands never invoke an implicit shell."""

from __future__ import annotations

import ast
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src" / "qzx"

_DIRECT_SHELL_CALLS = {
    "asyncio.create_subprocess_shell",
    "os.popen",
    "os.system",
    "subprocess.getoutput",
    "subprocess.getstatusoutput",
}
_SUBPROCESS_CALLS = {
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "subprocess.Popen",
    "subprocess.run",
}


def _dotted_name(node):
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return None


def _shell_violations():
    violations = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        relative = path.relative_to(REPOSITORY_ROOT)
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = _dotted_name(node.func)
            if called in _DIRECT_SHELL_CALLS:
                violations.append(
                    f"{relative}:{node.lineno}: direct shell call {called}"
                )
                continue
            if called not in _SUBPROCESS_CALLS:
                continue
            shell_keyword = next(
                (keyword for keyword in node.keywords if keyword.arg == "shell"),
                None,
            )
            if shell_keyword is None:
                continue
            explicitly_false = (
                isinstance(shell_keyword.value, ast.Constant)
                and shell_keyword.value.value is False
            )
            if not explicitly_false:
                violations.append(
                    f"{relative}:{node.lineno}: {called} uses a shell value that "
                    "is not literal False"
                )
    return violations


def test_qzx_source_never_invokes_an_implicit_command_shell():
    violations = _shell_violations()

    assert violations == [], (
        "Implicit shell execution expands injection and quoting risk. Pass an "
        "argv list to subprocess with shell=False instead:\n"
        + "\n".join(violations)
    )

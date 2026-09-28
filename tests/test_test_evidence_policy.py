"""Prevent test substitutions from masquerading as integration evidence."""

import ast
from pathlib import Path
import re
import tempfile


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


_FORBIDDEN_EVIDENCE_CALLS = frozenset(
    {
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
    }
)


def _runtime_policy_violations(test_file: Path) -> list[str]:
    """Return runtime-patching or silent-evidence violations for one test file."""

    tree = ast.parse(
        test_file.read_text(encoding="utf-8"),
        filename=str(test_file),
    )
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in {"unittest.mock", "mock"}:
            violations.append(f"{test_file}:{node.lineno}: runtime mock import")
        elif isinstance(node, ast.Import):
            for imported in node.names:
                if imported.name in {"unittest.mock", "mock"}:
                    violations.append(f"{test_file}:{node.lineno}: runtime mock import")
        elif isinstance(node, ast.Call):
            dotted_name = _dotted_name(node.func)
            if dotted_name == "monkeypatch.setattr":
                violations.append(f"{test_file}:{node.lineno}: monkeypatch.setattr")
            if dotted_name in _FORBIDDEN_EVIDENCE_CALLS:
                violations.append(f"{test_file}:{node.lineno}: silent skip/xfail")
    return violations


def test_suite_never_revokes_runner_filesystem_access():
    """Permission-failure tests inject errors; they never poison the real disk."""

    forbidden = (
        (r"\.chmod\(\s*0\s*\)", "chmod(0)"),
        (r"os\.chmod\([^\n,]+,\s*0\s*\)", "os.chmod(..., 0)"),
        (r"(?i)icacls[^\n]*/deny", "icacls /deny"),
        (r"(?i)icacls[^\n]*/inheritance:r", "icacls inheritance removal"),
        (r"(?i)\bSet-Acl\b", "Set-Acl"),
        (r"\bSetNamedSecurityInfo\b", "protected DACL mutation"),
        (r"\bFILE_ATTRIBUTE_READONLY\b", "read-only file attribute"),
        (r"(?i)\battrib\s+\+r\b", "attrib +R"),
        (r"\bTemporaryDirectory\s*\(", "TemporaryDirectory private ACL"),
        (r"\bmkdtemp\s*\(", "mkdtemp private ACL"),
    )
    violations = []
    this_file = Path(__file__).resolve()

    for test_file in sorted(TEST_ROOT.rglob("*.py")):
        if test_file.resolve() == this_file:
            continue
        source = test_file.read_text(encoding="utf-8")
        for pattern, label in forbidden:
            for match in re.finditer(pattern, source):
                line = source.count("\n", 0, match.start()) + 1
                violations.append(
                    f"{test_file}:{line}: forbidden real permission mutation ({label})"
                )

    assert violations == [], (
        "Tests must inject PermissionError/AccessDenied through a QZX-owned "
        "boundary instead of revoking access on the runner filesystem:\n"
        + "\n".join(violations)
    )


def test_qzx_owns_an_inheritable_tmp_path_fixture():
    """The suite must never fall back to pytest\'s mode=0o700 tmp_path root."""

    conftest = TEST_ROOT.parent / "conftest.py"
    source = conftest.read_text(encoding="utf-8")
    assert "QZX_INHERITABLE_TMP_V1" in source
    assert "def tmp_path(" in source
    assert "path.mkdir(mode=0o777)" in source
    assert 'getattr(pytestconfig.option, "basetemp", None)' in source
    assert 'root = parent / "q"' in source
    assert "tmp_path_factory" not in source


def test_qzx_tmp_path_uses_safe_session_root(tmp_path, pytestconfig):
    """QZX temp paths follow basetemp when available and inherit normal ACLs."""

    configured_basetemp = getattr(pytestconfig.option, "basetemp", None)
    if configured_basetemp:
        assert tmp_path.is_relative_to(Path(configured_basetemp).resolve())
    else:
        assert tmp_path.parent.parent == Path(tempfile.gettempdir()).resolve()


def test_suite_does_not_runtime_patch_dependencies_or_skip_evidence():
    """Runtime patching and silent skips require redesign, not an exception."""

    violations = []
    this_file = Path(__file__).resolve()
    for test_file in sorted(TEST_ROOT.rglob("*.py")):
        if test_file.resolve() != this_file:
            violations.extend(_runtime_policy_violations(test_file))

    assert violations == [], (
        "Tests must use real boundaries or explicit injected deterministic "
        "fakes; runtime patching and silent skips cannot certify behavior:\n"
        + "\n".join(violations)
    )

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "src" / "qzx" / "resources" / "product-manifest.json"


def test_python_compatibility_policy_is_consistent():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    development = manifest["channels"]["development"]
    compatibility = manifest["compatibility"]
    python_policy = compatibility["python"]

    assert development["requires_python"] == ">=3.13"
    assert python_policy["certified_runtime"] == "CPython 3.13.x"
    assert python_policy["certified_build"] == "standard"
    assert "free-threaded" in python_policy["statement"]["en"]
    assert "PyPy" in python_policy["statement"]["en"]
    assert "free-threaded" in python_policy["statement"]["es"]
    assert "PyPy" in python_policy["statement"]["es"]
    assert {
        (entry["os"], entry["python"])
        for entry in compatibility["ci"]["matrix"]
    } == {
        ("windows-latest", "3.13"),
        ("ubuntu-latest", "3.13"),
        ("macos-latest", "3.13"),
    }


def test_packaging_and_ci_read_the_canonical_policy():
    setup = (PROJECT_ROOT / "setup.py").read_text(encoding="utf-8")
    workflow = (
        PROJECT_ROOT / ".github" / "workflows" / "test.yml"
    ).read_text(encoding="utf-8")
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'python_requires=DEVELOPMENT_CHANNEL["requires_python"]' in setup
    assert '"Programming Language :: Python :: 3.13"' in setup
    assert '"Programming Language :: Python :: Implementation :: CPython"' in setup
    for unsupported_classifier in ("3.9", "3.10", "3.11", "3.12"):
        assert (
            f'"Programming Language :: Python :: {unsupported_classifier}"'
            not in setup
        )
    assert 'python: ["3.13"]' in workflow
    assert "target-version = ['py313']" in pyproject

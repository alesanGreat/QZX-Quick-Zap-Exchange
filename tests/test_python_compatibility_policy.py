import ast
import json
import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "src" / "qzx" / "resources" / "product-manifest.json"
TEST_ENVIRONMENTS_PATH = (
    PROJECT_ROOT / "src" / "qzx" / "resources" / "test-environments.json"
)


def test_python_compatibility_policy_is_consistent():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    test_environments = json.loads(
        TEST_ENVIRONMENTS_PATH.read_text(encoding="utf-8")
    )
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
    assert compatibility["ci"] == {
        "test_environments_source": "src/qzx/resources/test-environments.json"
    }
    assert test_environments["runtime"] == {
        "implementation": "CPython",
        "version": "3.13",
        "build": "standard",
        "display": {
            "en": "the standard CPython 3.13 build",
            "es": "la compilación estándar de CPython 3.13",
        },
    }
    assert {
        environment["id"] for environment in test_environments["environments"]
    } == {
        "windows",
        "ubuntu",
        "macos",
        "alpine-linux",
        "freebsd",
        "openbsd",
        "omnios",
        "oracle-solaris",
    }


def test_test_environment_source_matches_workflows_and_readme():
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "sync_test_environments.py"),
            "--check",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


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


def test_freebsd_15_1_release_amd64_workflow_is_explicit():
    workflow_path = (
        PROJECT_ROOT
        / ".github"
        / "workflows"
        / "test-freebsd-15.1-release-amd64.yml"
    )
    workflow = workflow_path.read_text(encoding="utf-8")

    assert workflow.startswith(
        "name: QZX tests | FreeBSD 15.1-RELEASE amd64 | CPython 3.13\n"
    )
    assert (
        "name: QZX test suite | FreeBSD 15.1-RELEASE amd64 | CPython 3.13"
        in workflow
    )
    assert "test-freebsd-15-1-release-amd64:" in workflow
    assert 'release: "15.1"' in workflow
    assert "arch: x86_64" in workflow
    assert 'test "$machine_arch" = "amd64"' in workflow
    assert "freebsd-version -u" in workflow
    assert (
        "vmactions/freebsd-vm@77ed28d336d03fe19a3f4f7266c1d2c4714dd79d"
        in workflow
    )


def test_additional_distribution_workflow_names_are_explicit():
    workflow_contracts = (
        (
            "test-alpine-linux-3.24.1-amd64.yml",
            "Alpine Linux 3.24.1 amd64",
            "test-alpine-linux-3-24-1-amd64:",
            (
                "python:3.13.14-alpine3.24"
                "@sha256:c25cd44f45df1279a2cba589e67dfcd9db04647ea483b117a7de8b1a99bdfb23"
            ),
        ),
        (
            "test-omnios-r151054-lts-x86_64.yml",
            "OmniOS r151054 LTS x86_64",
            "test-omnios-r151054-lts-x86-64:",
            (
                "vmactions/omnios-vm"
                "@027e3ec08fed6fb740ab5f300c2605f9de02997a"
            ),
        ),
        (
            "test-openbsd-7.9-amd64.yml",
            "OpenBSD 7.9 amd64",
            "test-openbsd-7-9-amd64:",
            (
                "vmactions/openbsd-vm"
                "@c941015845c0f0c429676840963dc63b226d4f69"
            ),
        ),
        (
            "test-oracle-solaris-11.4-cbe-x86_64.yml",
            "Oracle Solaris 11.4 CBE x86_64",
            "test-oracle-solaris-11-4-cbe-x86-64:",
            (
                "vmactions/solaris-vm"
                "@315163f088b66e55bbcc45928bd224d4973b2312"
            ),
        ),
    )

    for filename, distribution_name, job_id, pinned_runtime in workflow_contracts:
        workflow = (
            PROJECT_ROOT / ".github" / "workflows" / filename
        ).read_text(encoding="utf-8")

        assert workflow.startswith(
            f"name: QZX tests | {distribution_name} | CPython 3.13\n"
        )
        assert (
            f"name: QZX test suite | {distribution_name} | CPython 3.13"
            in workflow
        )
        assert job_id in workflow
        assert pinned_runtime in workflow


def test_oracle_solaris_no_deps_install_covers_package_dependencies():
    """Keep the exceptional --no-deps workflow aligned with setup.py."""
    setup_source = (PROJECT_ROOT / "setup.py").read_text(encoding="utf-8")
    setup_tree = ast.parse(setup_source)
    install_requires = None
    for node in setup_tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "install_requires"
            for target in node.targets
        ):
            install_requires = ast.literal_eval(node.value)
            break

    assert install_requires is not None
    workflow = (
        PROJECT_ROOT
        / ".github"
        / "workflows"
        / "test-oracle-solaris-11.4-cbe-x86_64.yml"
    ).read_text(encoding="utf-8").lower()
    applicable_names = {
        re.match(r"[a-z0-9_.-]+", requirement, re.IGNORECASE).group(0).lower()
        for requirement in install_requires
        if "platform_system == 'Windows'" not in requirement
    }

    missing = sorted(name for name in applicable_names if name not in workflow)
    assert missing == [], (
        "The Oracle Solaris --no-deps workflow omits package dependencies: "
        + ", ".join(missing)
    )

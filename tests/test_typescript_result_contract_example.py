"""Policy checks for the dependency-free TypeScript Result Contract producer."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = REPOSITORY_ROOT / "examples" / "result_contract"
PRODUCER = EXAMPLE_ROOT / "typescript-minimal.ts"
DEMO = EXAMPLE_ROOT / "typescript-minimal.demo.ts"
TYPECHECK = EXAMPLE_ROOT / "typescript-minimal.typecheck.ts"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "test.yml"
README = EXAMPLE_ROOT / "README.md"
QUICKSTART = REPOSITORY_ROOT / "docs" / "result-contract-quickstart.md"


def test_typescript_producer_is_importable_and_reserves_outcome_fields():
    producer = PRODUCER.read_text(encoding="utf-8")

    for public_symbol in (
        "export type QzxSuccess",
        "export type QzxFailure",
        "export type QzxResult",
        "export function qzxSuccess",
        "export function qzxFailure",
    ):
        assert public_symbol in producer
    for reserved_field in ("success", "message", "error", "error_code"):
        assert f'"{reserved_field}"' in producer
    assert "Object.prototype.hasOwnProperty.call" in producer
    assert "ERROR_CODE_PATTERN = /^[a-z][a-z0-9_]*$/" in producer
    assert "console.log" not in producer


def test_typescript_demo_and_negative_type_cases_are_separate_from_the_module():
    demo = DEMO.read_text(encoding="utf-8")
    typecheck = TYPECHECK.read_text(encoding="utf-8")

    assert 'from "./typescript-minimal.js"' in demo
    assert demo.count("console.log(JSON.stringify(") == 2
    assert typecheck.count("@ts-expect-error") >= 4
    assert "type QzxResult" in typecheck
    assert "result.success ?" in typecheck


def test_typescript_ci_is_pinned_strict_and_checkout_clean():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "result-contract-typescript:" in workflow
    assert "typescript@5.9.3" in workflow
    assert "npm install --global --prefix" in workflow
    assert "--ignore-scripts --no-audit --no-fund" in workflow
    assert 'npm_prefix="${RUNNER_TEMP}/qzx-typescript"' in workflow
    assert 'output_dir="${RUNNER_TEMP}/qzx-typescript-output"' in workflow
    assert "--noEmit --strict --exactOptionalPropertyTypes" in workflow
    assert "typescript-minimal.typecheck.ts" in workflow
    assert "typescript-minimal.demo.ts" in workflow
    assert "node_modules" not in workflow.split(
        "  result-contract-typescript:", 1
    )[1].split("\n  result-contract-conformance-action:", 1)[0]
    assert "producer.qzxSuccess" in workflow
    assert "producer.qzxFailure" in workflow


def test_typescript_documentation_points_to_all_verified_surfaces():
    readme = README.read_text(encoding="utf-8")
    quickstart = QUICKSTART.read_text(encoding="utf-8")

    for document in (readme, quickstart):
        assert "typescript-minimal.ts" in document
        assert "typescript-minimal.demo.ts" in document
        assert "typescript-minimal.typecheck.ts" in document
    assert "typescript@5.9.3" in readme
    assert "--exactOptionalPropertyTypes" in readme

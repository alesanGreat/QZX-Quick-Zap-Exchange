"""Focused tests for shared scaffold helpers."""

import pytest

from qzx.commands.development._scaffold_utils import (
    normalize_project_name,
    prepare_scaffold_project,
)


@pytest.mark.parametrize(
    ("name", "options", "expected"),
    [
        ("9 My-App!", {"leading_prefix": "py_"}, "py_9_my_app"),
        (
            "9 My-App!",
            {
                "replacement_characters": (" ",),
                "leading_prefix": "c_",
            },
            "c_9_myapp",
        ),
        (
            "9 My_App!",
            {
                "separator": "-",
                "replacement_characters": (" ", "_"),
            },
            "9-my-app",
        ),
        (
            "9 My-App!",
            {
                "leading_prefix": "cs_",
                "lowercase": False,
            },
            "cs_9_My_App",
        ),
        ("!?", {"leading_prefix": "py_"}, ""),
    ],
)
def test_normalize_project_name_preserves_ecosystem_rules(name, options, expected):
    assert normalize_project_name(name, **options) == expected


def test_prepare_scaffold_project_preserves_result_shape_and_field_order(tmp_path):
    result = prepare_scaffold_project(
        "sample",
        str(tmp_path),
        {"with_tests": True, "build_tool": "example"},
    )

    assert result["success"] is True
    assert list(result) == [
        "success",
        "project_name",
        "project_path",
        "with_tests",
        "build_tool",
        "files_created",
        "timestamp",
    ]
    assert result["files_created"] == [str(tmp_path / "sample")]
    assert (tmp_path / "sample").is_dir()


def test_prepare_scaffold_project_preserves_validation_errors(tmp_path):
    invalid_name = prepare_scaffold_project("", str(tmp_path), {})
    missing_path = prepare_scaffold_project(
        "sample",
        str(tmp_path / "missing"),
        {},
    )
    (tmp_path / "existing").mkdir()
    existing_project = prepare_scaffold_project("existing", str(tmp_path), {})

    assert invalid_name == {
        "success": False,
        "error": "Invalid project name",
        "message": (
            "Project name cannot be empty and must contain valid characters "
            "(letters, numbers, underscores)."
        ),
    }
    assert missing_path["error"] == f"Path does not exist: {tmp_path / 'missing'}"
    assert existing_project["error"] == (
        f"Project directory already exists: {tmp_path / 'existing'}"
    )

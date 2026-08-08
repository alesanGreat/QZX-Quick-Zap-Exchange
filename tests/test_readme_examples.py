import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPOSITORY_ROOT / "README.md"
README_FIND_FILES_EXAMPLE = re.compile(
    r'qzx findFiles (?P<path>examples/qzx_in_action) "\*\.txt" -r(?: --json)?'
)


def test_readme_find_files_fixture_is_present_and_usable():
    readme = README_PATH.read_text(encoding="utf-8")
    referenced_paths = [
        match.group("path")
        for match in README_FIND_FILES_EXAMPLE.finditer(readme)
    ]

    assert referenced_paths == [
        "examples/qzx_in_action",
        "examples/qzx_in_action",
    ]

    fixture_directory = REPOSITORY_ROOT / referenced_paths[0]
    assert fixture_directory.is_dir()

    fixture_files = sorted(fixture_directory.glob("*.txt"))
    assert [path.name for path in fixture_files] == ["alpha.txt", "beta.txt"]
    assert all(path.read_text(encoding="utf-8").strip() for path in fixture_files)

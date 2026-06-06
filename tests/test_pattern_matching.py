"""Basic wildcard matching coverage used by file-search commands."""

import fnmatch


def test_python_file_pattern_matching():
    pattern = "*.py"
    expected = {
        "methods.py": True,
        "config.py": True,
        "detect.py": True,
        "test_file.txt": False,
    }

    assert {
        filename: fnmatch.fnmatch(filename, pattern) for filename in expected
    } == expected

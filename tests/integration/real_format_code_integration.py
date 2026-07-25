"""Run formatCode against every real formatter it claims to support."""

from pathlib import Path
import shutil

import pytest

from qzx.commands.development.format_code import FormatCodeCommand


FORMAT_CASES = [
    (
        "python",
        "sample.py",
        "def greet( name:str)->str:\n return 'hello '+name\n",
    ),
    (
        "javascript",
        "sample.js",
        "const value={alpha:1,beta:[2,3]};\n",
    ),
    (
        "typescript",
        "sample.ts",
        "const value:{alpha:number}={alpha:1};\n",
    ),
    (
        "rust",
        "sample.rs",
        'fn main(){println!("hello");}\n',
    ),
    (
        "go",
        "sample.go",
        'package main\nimport "fmt"\nfunc main(){fmt.Println("hello")}\n',
    ),
    (
        "php",
        "sample.php",
        "<?php\nfunction greet( $name ){return 'hello '.$name;}\n",
    ),
    (
        "c",
        "sample.c",
        '#include <stdio.h>\nint main(){printf("hello");return 0;}\n',
    ),
    (
        "cpp",
        "sample.cpp",
        '#include <iostream>\nint main(){std::cout<<"hello";return 0;}\n',
    ),
]


@pytest.mark.parametrize(
    ("language", "filename", "unformatted_source"),
    FORMAT_CASES,
)
def test_format_code_really_formats_and_then_verifies_each_language(
    tmp_path,
    language,
    filename,
    unformatted_source,
):
    formatter = FormatCodeCommand.FORMATTERS[language]["tool"]
    assert shutil.which(formatter), (
        f"the dedicated real-formatter workflow must install {formatter}"
    )

    source_path = tmp_path / filename
    source_path.write_text(unformatted_source, encoding="utf-8")

    formatted = FormatCodeCommand().execute(
        str(source_path),
        language=language,
        dry_run=False,
    )

    assert formatted["success"] is True, formatted
    assert formatted["all_succeeded"] is True, formatted
    assert formatted["formatted_count"] == 1
    assert formatted["failed_count"] == 0
    assert formatted["unavailable_tools"] == []
    assert source_path.read_text(encoding="utf-8") != unformatted_source

    verification = FormatCodeCommand().execute(
        str(source_path),
        language=language,
        dry_run=True,
    )

    assert verification["success"] is True, verification
    assert verification["all_succeeded"] is True, verification
    assert verification["formatted_count"] == 0
    assert verification["skipped_count"] == 1
    assert verification["failed_count"] == 0


def test_all_declared_formatters_have_real_integration_cases():
    covered_languages = {case[0] for case in FORMAT_CASES}

    assert covered_languages == set(FormatCodeCommand.FORMATTERS)

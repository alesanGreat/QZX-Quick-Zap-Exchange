#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the various scaffolding commands
"""

import os
from qzx.commands.development.scaffold_python import MakeScaffProgramPythonCommand
from qzx.commands.development.scaffold_rust import MakeScaffProgramRustCommand
from qzx.commands.development.scaffold_javascript import MakeScaffProgramJavascriptCommand
from qzx.commands.development.scaffold_typescript import MakeScaffProgramTypescriptCommand
from qzx.commands.development.scaffold_php import MakeScaffProgramPhpCommand
from qzx.commands.development.scaffold_c import MakeScaffProgramCCommand
from qzx.commands.development.scaffold_cpp import MakeScaffProgramCppCommand

class TestScaffoldCommands:
    """
    Tests for scaffolding commands
    """
    
    def test_scaffold_python(self, tmp_path):
        cmd = MakeScaffProgramPythonCommand()
        result = cmd.execute("my_py_app", str(tmp_path), with_tests="true", create_venv="false")
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my_py_app")
        assert os.path.isfile(tmp_path / "my_py_app" / "main.py")
        assert os.path.isdir(tmp_path / "my_py_app" / "tests")

    def test_scaffold_rust(self, tmp_path):
        cmd = MakeScaffProgramRustCommand()
        result = cmd.execute("my_rust_app", str(tmp_path), binary="true", with_tests="true")
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my_rust_app")
        assert os.path.isfile(tmp_path / "my_rust_app" / "Cargo.toml")
        assert os.path.isfile(tmp_path / "my_rust_app" / "src" / "main.rs")

    def test_scaffold_javascript(self, tmp_path):
        cmd = MakeScaffProgramJavascriptCommand()
        result = cmd.execute("my_js_app", str(tmp_path), with_tests="true")
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my-js-app")
        assert os.path.isfile(tmp_path / "my-js-app" / "package.json")
        assert os.path.isfile(tmp_path / "my-js-app" / "index.js")
        assert os.path.isdir(tmp_path / "my-js-app" / "tests")
        assert os.path.isfile(tmp_path / "my-js-app" / "tests" / "index.test.js")

    def test_scaffold_typescript(self, tmp_path):
        cmd = MakeScaffProgramTypescriptCommand()
        result = cmd.execute("my_ts_app", str(tmp_path), with_tests="true")
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my-ts-app")
        assert os.path.isfile(tmp_path / "my-ts-app" / "package.json")
        assert os.path.isfile(tmp_path / "my-ts-app" / "tsconfig.json")
        assert os.path.isfile(tmp_path / "my-ts-app" / "src" / "index.ts")
        assert os.path.isdir(tmp_path / "my-ts-app" / "tests")
        assert os.path.isfile(tmp_path / "my-ts-app" / "tests" / "index.test.ts")

    def test_scaffold_php(self, tmp_path):
        cmd = MakeScaffProgramPhpCommand()
        result = cmd.execute("my_php_app", str(tmp_path), with_tests="true")
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my-php-app")
        assert os.path.isfile(tmp_path / "my-php-app" / "composer.json")
        assert os.path.isfile(tmp_path / "my-php-app" / "index.php")
        assert os.path.isfile(tmp_path / "my-php-app" / "src" / "Core.php")
        assert os.path.isdir(tmp_path / "my-php-app" / "tests")
        assert os.path.isfile(tmp_path / "my-php-app" / "tests" / "CoreTest.php")

    def test_scaffold_c(self, tmp_path):
        cmd = MakeScaffProgramCCommand()
        result = cmd.execute("my_c_app", str(tmp_path), build_system="cmake")
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my_c_app")
        assert os.path.isfile(tmp_path / "my_c_app" / "CMakeLists.txt")
        assert os.path.isfile(tmp_path / "my_c_app" / "src" / "main.c")

    def test_scaffold_cpp(self, tmp_path):
        cmd = MakeScaffProgramCppCommand()
        result = cmd.execute("my_cpp_app", str(tmp_path))
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my_cpp_app")
        assert os.path.isfile(tmp_path / "my_cpp_app" / "CMakeLists.txt")
        assert os.path.isfile(tmp_path / "my_cpp_app" / "src" / "main.cpp")

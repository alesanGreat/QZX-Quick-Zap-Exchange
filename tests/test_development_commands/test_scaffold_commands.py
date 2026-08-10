#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the various scaffolding commands
"""

import os
import subprocess

from qzx.commands.development.scaffold_python import ScaffoldPythonCommand
from qzx.commands.development.scaffold_rust import ScaffoldRustCommand
from qzx.commands.development.scaffold_javascript import ScaffoldJavaScriptCommand
from qzx.commands.development.scaffold_typescript import ScaffoldTypeScriptCommand
from qzx.commands.development.scaffold_php import ScaffoldPhpCommand
from qzx.commands.development.scaffold_c import ScaffoldCCommand
from qzx.commands.development.scaffold_cpp import ScaffoldCppCommand
from qzx.commands.development.scaffold_go import ScaffoldGoCommand
from qzx.commands.development.scaffold_java import ScaffoldJavaCommand
from qzx.commands.development.scaffold_kotlin import ScaffoldKotlinCommand
from qzx.commands.development.scaffold_csharp import ScaffoldCSharpCommand

class TestScaffoldCommands:
    """
    Tests for scaffolding commands
    """
    
    def test_scaffold_python(self, tmp_path):
        cmd = ScaffoldPythonCommand()
        result = cmd.execute("my_py_app", str(tmp_path), with_tests="true", create_venv="false")
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my_py_app")
        assert os.path.isfile(tmp_path / "my_py_app" / "main.py")
        assert os.path.isdir(tmp_path / "my_py_app" / "tests")

    def test_scaffold_rust(self, tmp_path):
        cmd = ScaffoldRustCommand()
        result = cmd.execute("my_rust_app", str(tmp_path), binary="true", with_tests="true")
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my_rust_app")
        assert os.path.isfile(tmp_path / "my_rust_app" / "Cargo.toml")
        assert os.path.isfile(tmp_path / "my_rust_app" / "src" / "main.rs")

    def test_scaffold_javascript(self, tmp_path):
        cmd = ScaffoldJavaScriptCommand()
        result = cmd.execute("my_js_app", str(tmp_path), with_tests="true")
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my-js-app")
        assert os.path.isfile(tmp_path / "my-js-app" / "package.json")
        assert os.path.isfile(tmp_path / "my-js-app" / "index.js")
        assert os.path.isdir(tmp_path / "my-js-app" / "tests")
        assert os.path.isfile(tmp_path / "my-js-app" / "tests" / "index.test.js")

    def test_scaffold_rejects_ambiguous_boolean_before_creating_project(
        self, tmp_path
    ):
        result = ScaffoldJavaScriptCommand().execute(
            "ambiguous",
            str(tmp_path),
            with_tests="perhaps",
        )

        assert result["success"] is False
        assert "with_tests must be true or false" in result["message"]
        assert not (tmp_path / "ambiguous").exists()

    def test_scaffold_typescript(self, tmp_path):
        cmd = ScaffoldTypeScriptCommand()
        result = cmd.execute("my_ts_app", str(tmp_path), with_tests="true")
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my-ts-app")
        assert os.path.isfile(tmp_path / "my-ts-app" / "package.json")
        assert os.path.isfile(tmp_path / "my-ts-app" / "tsconfig.json")
        assert os.path.isfile(tmp_path / "my-ts-app" / "src" / "index.ts")
        assert os.path.isdir(tmp_path / "my-ts-app" / "tests")
        assert os.path.isfile(tmp_path / "my-ts-app" / "tests" / "index.test.ts")

    def test_scaffold_php(self, tmp_path):
        cmd = ScaffoldPhpCommand()
        result = cmd.execute("my_php_app", str(tmp_path), with_tests="true")
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my-php-app")
        assert os.path.isfile(tmp_path / "my-php-app" / "composer.json")
        assert os.path.isfile(tmp_path / "my-php-app" / "index.php")
        assert os.path.isfile(tmp_path / "my-php-app" / "src" / "Core.php")
        assert os.path.isdir(tmp_path / "my-php-app" / "tests")
        assert os.path.isfile(tmp_path / "my-php-app" / "tests" / "CoreTest.php")

    def test_scaffold_c(self, tmp_path):
        cmd = ScaffoldCCommand()
        result = cmd.execute("my_c_app", str(tmp_path), build_system="cmake")
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my_c_app")
        assert os.path.isfile(tmp_path / "my_c_app" / "CMakeLists.txt")
        assert os.path.isfile(tmp_path / "my_c_app" / "src" / "main.c")

    def test_scaffold_cpp(self, tmp_path):
        cmd = ScaffoldCppCommand()
        result = cmd.execute("my_cpp_app", str(tmp_path))
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my_cpp_app")
        assert os.path.isfile(tmp_path / "my_cpp_app" / "CMakeLists.txt")
        assert os.path.isfile(tmp_path / "my_cpp_app" / "src" / "main.cpp")

    def test_scaffold_go(self, tmp_path):
        cmd = ScaffoldGoCommand()
        result = cmd.execute("my_go_app", str(tmp_path), with_tests="true")
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my_go_app")
        assert os.path.isfile(tmp_path / "my_go_app" / "go.mod")
        assert os.path.isfile(tmp_path / "my_go_app" / "main.go")
        assert os.path.isfile(tmp_path / "my_go_app" / "main_test.go")

    def test_scaffold_java(self, tmp_path):
        cmd = ScaffoldJavaCommand()
        result = cmd.execute("my_java_app", str(tmp_path), with_tests="true")
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my_java_app")
        assert os.path.isfile(tmp_path / "my_java_app" / "pom.xml")
        assert os.path.isfile(tmp_path / "my_java_app" / "src" / "main" / "java" / "com" / "example" / "my_java_app" / "App.java")
        assert os.path.isfile(tmp_path / "my_java_app" / "src" / "test" / "java" / "com" / "example" / "my_java_app" / "AppTest.java")

    def test_scaffold_kotlin(self, tmp_path):
        cmd = ScaffoldKotlinCommand()
        result = cmd.execute("my_kotlin_app", str(tmp_path), with_tests="true")
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my_kotlin_app")
        assert os.path.isfile(tmp_path / "my_kotlin_app" / "build.gradle.kts")
        assert os.path.isfile(tmp_path / "my_kotlin_app" / "settings.gradle.kts")
        assert os.path.isfile(tmp_path / "my_kotlin_app" / "src" / "main" / "kotlin" / "com" / "example" / "my_kotlin_app" / "App.kt")
        assert os.path.isfile(tmp_path / "my_kotlin_app" / "src" / "test" / "kotlin" / "com" / "example" / "my_kotlin_app" / "AppTest.kt")

    def test_scaffold_csharp(self, tmp_path):
        cmd = ScaffoldCSharpCommand()
        result = cmd.execute("my_csharp_app", str(tmp_path), with_tests="true")
        assert result["success"] is True
        assert os.path.isdir(tmp_path / "my_csharp_app")
        assert os.path.isfile(tmp_path / "my_csharp_app" / "my_csharp_app.csproj")
        assert os.path.isfile(tmp_path / "my_csharp_app" / "Program.cs")
        assert os.path.isfile(tmp_path / "my_csharp_app" / "my_csharp_app.sln")
        assert os.path.isdir(tmp_path / "my_csharp_app" / "my_csharp_app.Tests")
        assert os.path.isfile(tmp_path / "my_csharp_app" / "my_csharp_app.Tests" / "ProgramTests.cs")

    def test_scaffold_csharp_dotnet_probe_times_out_fail_closed(self):
        calls = []

        def timed_out_runner(args, **kwargs):
            calls.append((args, kwargs))
            raise subprocess.TimeoutExpired(args, kwargs["timeout"])

        cmd = ScaffoldCSharpCommand()
        assert cmd._is_dotnet_installed(timed_out_runner) is False
        assert calls[0][0] == ["dotnet", "--version"]
        assert calls[0][1]["timeout"] == 5.0

    def test_scaffold_csharp_dotnet_probe_rejects_nonzero_exit(self):
        def failed_runner(args, **kwargs):
            return subprocess.CompletedProcess(args=args, returncode=1)

        cmd = ScaffoldCSharpCommand()
        assert cmd._is_dotnet_installed(failed_runner) is False

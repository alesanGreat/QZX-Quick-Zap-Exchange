#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the findDeadCode command
"""

import os
from qzx.commands.development.find_dead_code import FindDeadCodeCommand

class TestFindDeadCodeCommand:
    """
    Tests for the FindDeadCodeCommand class
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = FindDeadCodeCommand()
        
    def test_nonexistent_directory(self):
        """Test with a directory that does not exist"""
        result = self.command.execute("non_existent_dir_abc_123")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_find_dead_code_python(self, tmp_path):
        """Test identifying unused Python functions and classes"""
        # Create active module: defines used_func which is called in app.py
        used_module_content = (
            "def used_func():\n"
            "    return 'I am used'\n"
            "\n"
            "def unused_func():\n"
            "    return 'I am dead code'\n"
            "\n"
            "class UsedClass:\n"
            "    pass\n"
            "\n"
            "class UnusedClass:\n"
            "    pass\n"
        )
        # Create caller script: references used_func and UsedClass
        app_content = (
            "from utils import used_func, UsedClass\n"
            "print(used_func())\n"
            "obj = UsedClass()\n"
        )
        
        with open(tmp_path / "utils.py", "w", encoding="utf-8") as f:
            f.write(used_module_content)
        with open(tmp_path / "app.py", "w", encoding="utf-8") as f:
            f.write(app_content)
            
        result = self.command.execute(str(tmp_path))
        assert result["success"] is True
        
        # We expect unused_func and UnusedClass to be identified as dead code
        dead_names = [sym["name"] for sym in result["dead_symbols"]]
        assert "unused_func" in dead_names
        assert "UnusedClass" in dead_names
        
        # used_func and UsedClass should NOT be flagged as dead
        assert "used_func" not in dead_names
        assert "UsedClass" not in dead_names
        
        # Verify details
        unused_func_details = next(sym for sym in result["dead_symbols"] if sym["name"] == "unused_func")
        assert unused_func_details["type"] == "function"
        assert unused_func_details["file"] == "utils.py"
        
    def test_find_dead_code_js(self, tmp_path):
        """Test identifying unused JS/TS exported items"""
        # Module: defines active and dead exports
        js_module = (
            "export function activeExport() { return 1; }\n"
            "export class UnusedClassExport { constructor() {} }\n"
            "export const unusedConstExport = 42;\n"
        )
        # Caller: references activeExport
        js_app = (
            "import { activeExport } from './module';\n"
            "activeExport();\n"
        )
        
        with open(tmp_path / "module.js", "w", encoding="utf-8") as f:
            f.write(js_module)
        with open(tmp_path / "app.js", "w", encoding="utf-8") as f:
            f.write(js_app)
            
        result = self.command.execute(str(tmp_path))
        assert result["success"] is True
        
        dead_names = [sym["name"] for sym in result["dead_symbols"]]
        assert "UnusedClassExport" in dead_names
        assert "unusedConstExport" in dead_names
        assert "activeExport" not in dead_names

    def test_find_dead_code_php(self, tmp_path):
        """Test identifying unused PHP functions and classes"""
        php_lib = (
            "<?php\n"
            "class ActiveService {\n"
            "    public function handle() {}\n"
            "}\n"
            "class DeadService {\n"
            "    public function run() {}\n"
            "}\n"
            "function active_helper() {}\n"
            "function dead_helper() {}\n"
        )
        php_app = (
            "<?php\n"
            "$service = new ActiveService();\n"
            "active_helper();\n"
        )
        
        with open(tmp_path / "lib.php", "w", encoding="utf-8") as f:
            f.write(php_lib)
        with open(tmp_path / "app.php", "w", encoding="utf-8") as f:
            f.write(php_app)
            
        result = self.command.execute(str(tmp_path))
        assert result["success"] is True
        
        dead_names = [sym["name"] for sym in result["dead_symbols"]]
        assert "DeadService" in dead_names
        assert "dead_helper" in dead_names
        assert "ActiveService" not in dead_names
        assert "active_helper" not in dead_names

    def test_find_dead_code_rust(self, tmp_path):
        """Test identifying unused Rust functions and structs"""
        rust_lib = (
            "pub struct ActiveStruct {}\n"
            "pub struct DeadStruct {}\n"
            "pub fn active_fn() {}\n"
            "pub fn dead_fn() {}\n"
        )
        rust_app = (
            "use lib::{ActiveStruct, active_fn};\n"
            "fn main() {\n"
            "    let a = ActiveStruct {};\n"
            "    active_fn();\n"
            "}\n"
        )
        with open(tmp_path / "lib.rs", "w", encoding="utf-8") as f:
            f.write(rust_lib)
        with open(tmp_path / "main.rs", "w", encoding="utf-8") as f:
            f.write(rust_app)
            
        result = self.command.execute(str(tmp_path))
        assert result["success"] is True
        
        dead_names = [sym["name"] for sym in result["dead_symbols"]]
        assert "DeadStruct" in dead_names
        assert "dead_fn" in dead_names
        assert "ActiveStruct" not in dead_names
        assert "active_fn" not in dead_names

    def test_find_dead_code_cpp(self, tmp_path):
        """Test identifying unused C++ functions and classes"""
        cpp_lib = (
            "class ActiveClass {};\n"
            "class DeadClass {};\n"
            "void active_func() {}\n"
            "void dead_func() {}\n"
        )
        cpp_app = (
            "#include \"lib.hpp\"\n"
            "int main() {\n"
            "    ActiveClass a;\n"
            "    active_func();\n"
            "}\n"
        )
        with open(tmp_path / "lib.hpp", "w", encoding="utf-8") as f:
            f.write(cpp_lib)
        with open(tmp_path / "main.cpp", "w", encoding="utf-8") as f:
            f.write(cpp_app)
            
        result = self.command.execute(str(tmp_path))
        assert result["success"] is True
        
        dead_names = [sym["name"] for sym in result["dead_symbols"]]
        assert "DeadClass" in dead_names
        assert "dead_func" in dead_names
        assert "ActiveClass" not in dead_names
        assert "active_func" not in dead_names

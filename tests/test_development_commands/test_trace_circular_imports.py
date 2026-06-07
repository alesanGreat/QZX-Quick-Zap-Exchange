#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the traceCircularImports command
"""

import os
from qzx.commands.development.trace_circular_imports import TraceCircularImportsCommand

class TestTraceCircularImportsCommand:
    """
    Tests for the TraceCircularImportsCommand class
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = TraceCircularImportsCommand()
        
    def test_nonexistent_directory(self):
        """Test with a directory that does not exist"""
        result = self.command.execute("non_existent_dir_abc_123")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_no_circular_imports(self, tmp_path):
        """Test a clean workspace with linear imports"""
        # Module A
        with open(tmp_path / "a.py", "w", encoding="utf-8") as f:
            f.write("import b\nprint('A')\n")
        # Module B
        with open(tmp_path / "b.py", "w", encoding="utf-8") as f:
            f.write("print('B')\n")
            
        result = self.command.execute(str(tmp_path))
        assert result["success"] is True
        assert result["cycles_count"] == 0
        assert result["cycles"] == []
        assert "No circular import dependencies detected" in result["message"]
        
    def test_simple_circular_import(self, tmp_path):
        """Test with a direct two-module circular import cycle A -> B -> A"""
        # Module A: imports b
        with open(tmp_path / "a.py", "w", encoding="utf-8") as f:
            f.write("import b\n")
        # Module B: imports a
        with open(tmp_path / "b.py", "w", encoding="utf-8") as f:
            f.write("import a\n")
            
        result = self.command.execute(str(tmp_path))
        assert result["success"] is True
        assert result["cycles_count"] == 1
        
        # Verify cycle pathway
        cycle = result["cycles"][0]
        # Should contain both modules and return to the starting one
        assert "a.py" in cycle
        assert "b.py" in cycle
        assert cycle[0] == cycle[-1] # closes the loop
        
    def test_three_module_circular_import(self, tmp_path):
        """Test with a three-module circular import cycle A -> B -> C -> A"""
        with open(tmp_path / "a.py", "w", encoding="utf-8") as f:
            f.write("import b\n")
        with open(tmp_path / "b.py", "w", encoding="utf-8") as f:
            f.write("from c import foo\n")
        with open(tmp_path / "c.py", "w", encoding="utf-8") as f:
            f.write("import a\nfoo = 42\n")
            
        result = self.command.execute(str(tmp_path))
        assert result["success"] is True
        assert result["cycles_count"] == 1
        
        cycle = result["cycles"][0]
        assert "a.py" in cycle
        assert "b.py" in cycle
        assert "c.py" in cycle
        assert len(cycle) == 4
        assert cycle[0] == cycle[-1]

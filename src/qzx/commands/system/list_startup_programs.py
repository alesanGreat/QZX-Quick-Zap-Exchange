#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ListStartupPrograms Command - Lists programs configured to run on system boot/login (Registry & Startup folder on Windows).
"""

from qzx.commands.system._startup_program_inventory import execute_startup_programs
from qzx.core.command_base import CommandBase

class ListStartupProgramsCommand(CommandBase):
    """
    Command to audit and list all startup programs configured to run on boot or login.
    """
    
    name = "listStartupPrograms"
    description = "Lists all startup programs configured to run on system boot or user login"
    category = "system"
    
    parameters = []
    
    examples = [
        {
            'command': 'qzx listStartupPrograms',
            'description': 'List all startup programs and registry triggers'
        }
    ]
    
    def execute(self):
        """List startup programs from the current platform's real sources."""
        return execute_startup_programs(self)

    @staticmethod
    def _startup_item(
        name,
        command,
        source,
        item_type,
        source_path=None,
    ):
        """Normalize a startup entry without inventing an executable target."""
        normalized_name = str(name or "").strip()
        normalized_command = str(command or "").strip()
        issues = []
        if not normalized_name:
            normalized_name = "(unnamed startup entry)"
            issues.append("The startup entry has no configured name.")
        if not normalized_command:
            issues.append(
                "The startup entry has an empty command and cannot launch a program."
            )

        result = {
            "name": normalized_name,
            "command": normalized_command,
            "source": source,
            "type": item_type,
            "actionable": bool(normalized_command),
            "issues": issues,
        }
        if source_path is not None:
            result["source_path"] = str(source_path)
        return result
        
    def _parse_desktop_file(self, filepath):
        """Extracts Name and Exec from desktop entry files on Unix"""
        name = None
        exec_cmd = None
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("Name="):
                    name = line.split("=", 1)[1].strip()
                elif line.startswith("Exec="):
                    exec_cmd = line.split("=", 1)[1].strip()
                if name and exec_cmd:
                    break
        return name, exec_cmd

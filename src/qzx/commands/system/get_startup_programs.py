#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetStartupPrograms Command - Lists programs configured to run on system boot/login (Registry & Startup folder on Windows).
"""

import os
import platform

from qzx.core.command_base import CommandBase

class GetStartupProgramsCommand(CommandBase):
    """
    Command to audit and list all startup programs configured to run on boot or login.
    """
    
    name = "getStartupPrograms"
    description = "Lists all startup programs configured to run on system boot or user login"
    category = "system"
    
    parameters = []
    
    examples = [
        {
            'command': 'qzx getStartupPrograms',
            'description': 'Retrieve a list of all startup programs and registry triggers'
        }
    ]
    
    def execute(self):
        """
        Retrieves startup program list
        
        Returns:
            Dictionary with startup applications details
        """
        is_windows = platform.system().lower() == "windows"
        
        startup_items = []
        errors = []
        
        if is_windows:
            # 1. Query Registry
            # Try winreg imports (only on Windows)
            try:
                import winreg
                
                # Check Registry Run Keys (HKCU and HKLM)
                reg_paths = [
                    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU\\Run"),
                    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU\\RunOnce"),
                    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM\\Run")
                ]
                
                for hkey, subkey, label in reg_paths:
                    try:
                        with winreg.OpenKey(hkey, subkey, 0, winreg.KEY_READ) as key:
                            info = winreg.QueryInfoKey(key)
                            value_count = info[1]
                            for i in range(value_count):
                                name, val, val_type = winreg.EnumValue(key, i)
                                startup_items.append(
                                    self._startup_item(
                                        name=name,
                                        command=val,
                                        source=label,
                                        item_type="registry",
                                    )
                                )
                    except PermissionError:
                        errors.append(f"Permission denied reading registry subkey: {label}")
                    except OSError:
                        # Key might not exist, skip silently
                        pass
            except ImportError:
                errors.append("Failed to import winreg on Windows system.")
                
            # 2. Check Startup Folders
            user_profile = os.environ.get("USERPROFILE", "")
            program_data = os.environ.get("ProgramData", "C:\\ProgramData")
            
            startup_folders = []
            if user_profile:
                startup_folders.append((
                    os.path.join(user_profile, r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup"),
                    "User Startup Folder"
                ))
            if program_data:
                startup_folders.append((
                    os.path.join(program_data, r"Microsoft\Windows\Start Menu\Programs\Startup"),
                    "All Users Startup Folder"
                ))
                
            for folder_path, label in startup_folders:
                if os.path.exists(folder_path) and os.path.isdir(folder_path):
                    try:
                        for item in os.listdir(folder_path):
                            full_path = os.path.join(folder_path, item)
                            if os.path.isfile(full_path):
                                startup_items.append(
                                    self._startup_item(
                                        name=item,
                                        command=full_path,
                                        source=label,
                                        item_type="directory",
                                        source_path=full_path,
                                    )
                                )
                    except Exception as e:
                        errors.append(f"Error reading startup folder '{folder_path}': {str(e)}")
                        
        else:
            # Unix-like system autostart checks
            home = os.environ.get("HOME", "")
            autostart_paths = []
            if home:
                autostart_paths.append((os.path.join(home, ".config/autostart"), "User Autostart"))
            autostart_paths.append(("/etc/xdg/autostart", "System Autostart"))
            
            for path, label in autostart_paths:
                if os.path.exists(path) and os.path.isdir(path):
                    try:
                        for item in os.listdir(path):
                            if item.endswith(".desktop"):
                                full_path = os.path.join(path, item)
                                name, cmd = self._parse_desktop_file(full_path)
                                startup_items.append(
                                    self._startup_item(
                                        name=name or item,
                                        command=cmd,
                                        source=label,
                                        item_type="desktop_file",
                                        source_path=full_path,
                                    )
                                )
                    except Exception as e:
                        errors.append(f"Error reading autostart folder '{path}': {str(e)}")
                        
        total_items = len(startup_items)
        actionable_items = sum(
            item["actionable"]
            for item in startup_items
        )
        entries_with_issues = sum(
            bool(item["issues"])
            for item in startup_items
        )
        msg = "Startup Programs Audit Summary:\n"
        msg += f"- Total startup items: {total_items}\n"
        msg += f"- Actionable entries: {actionable_items}\n"
        msg += f"- Entries requiring attention: {entries_with_issues}\n"
        
        if total_items > 0:
            msg += "\nDetected Startup Applications:\n"
            for item in startup_items:
                command = item["command"][:60] or "(empty command)"
                msg += (
                    f"  - [{item['source']}] {item['name']} -> "
                    f"Command: {command}\n"
                )
        else:
            msg += "- No startup entries identified."
            
        return {
            "success": True,
            "os": platform.system(),
            "total_startup_programs": total_items,
            "actionable_startup_programs": actionable_items,
            "entries_with_issues": entries_with_issues,
            "startup_programs": startup_items,
            "errors": errors,
            "message": msg
        }

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
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("Name="):
                        name = line.split("=", 1)[1].strip()
                    elif line.startswith("Exec="):
                        exec_cmd = line.split("=", 1)[1].strip()
                    if name and exec_cmd:
                        break
        except Exception:
            pass
        return name, exec_cmd

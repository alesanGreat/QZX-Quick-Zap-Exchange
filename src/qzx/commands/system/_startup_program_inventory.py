"""Startup-program discovery workflow for listStartupPrograms."""

from __future__ import annotations

import os
import platform


def _windows_registry(command, items, errors):
    try:
        import winreg
    except ImportError:
        errors.append("Failed to import winreg on Windows system.")
        return
    paths = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU\\Run"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU\\RunOnce"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM\\Run"),
    ]
    for hkey, subkey, label in paths:
        try:
            with winreg.OpenKey(hkey, subkey, 0, winreg.KEY_READ) as key:
                for index in range(winreg.QueryInfoKey(key)[1]):
                    name, value, _value_type = winreg.EnumValue(key, index)
                    items.append(
                        command._startup_item(
                            name=name,
                            command=value,
                            source=label,
                            item_type="registry",
                        )
                    )
        except PermissionError:
            errors.append(f"Permission denied reading registry subkey: {label}")
        except OSError:
            pass


def _startup_folders():
    folders = []
    user_profile = os.environ.get("USERPROFILE", "")
    program_data = os.environ.get("ProgramData", r"C:\ProgramData")
    if user_profile:
        folders.append(
            (
                os.path.join(
                    user_profile,
                    r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup",
                ),
                "User Startup Folder",
            )
        )
    if program_data:
        folders.append(
            (
                os.path.join(
                    program_data,
                    r"Microsoft\Windows\Start Menu\Programs\Startup",
                ),
                "All Users Startup Folder",
            )
        )
    return folders


def _windows_folders(command, items, errors):
    for folder_path, label in _startup_folders():
        if not os.path.isdir(folder_path):
            continue
        try:
            for name in os.listdir(folder_path):
                full_path = os.path.join(folder_path, name)
                if os.path.isfile(full_path):
                    items.append(
                        command._startup_item(
                            name=name,
                            command=full_path,
                            source=label,
                            item_type="directory",
                            source_path=full_path,
                        )
                    )
        except Exception as exc:
            errors.append(f"Error reading startup folder '{folder_path}': {str(exc)}")


def _unix_paths():
    paths = []
    home = os.environ.get("HOME", "")
    if home:
        paths.append((os.path.join(home, ".config/autostart"), "User Autostart"))
    paths.append(("/etc/xdg/autostart", "System Autostart"))
    return paths


def _unix_items(command, items, errors):
    for folder_path, label in _unix_paths():
        if not os.path.isdir(folder_path):
            continue
        try:
            for name in os.listdir(folder_path):
                if not name.endswith(".desktop"):
                    continue
                full_path = os.path.join(folder_path, name)
                display_name, launch = command._parse_desktop_file(full_path)
                items.append(
                    command._startup_item(
                        name=display_name or name,
                        command=launch,
                        source=label,
                        item_type="desktop_file",
                        source_path=full_path,
                    )
                )
        except Exception as exc:
            errors.append(f"Error reading autostart folder '{folder_path}': {str(exc)}")


def _summary_message(items, actionable, issues):
    message = "Startup Programs Audit Summary:\n"
    message += f"- Total startup items: {len(items)}\n"
    message += f"- Actionable entries: {actionable}\n"
    message += f"- Entries requiring attention: {issues}\n"
    if not items:
        return message + "- No startup entries identified."
    message += "\nDetected Startup Applications:\n"
    for item in items:
        launch = item["command"][:60] or "(empty command)"
        message += (
            f"  - [{item['source']}] {item['name']} -> Command: {launch}\n"
        )
    return message


def execute_startup_programs(command):
    """Run the public listStartupPrograms workflow."""
    items, errors = [], []
    if platform.system().lower() == "windows":
        _windows_registry(command, items, errors)
        _windows_folders(command, items, errors)
    else:
        _unix_items(command, items, errors)
    actionable = sum(item["actionable"] for item in items)
    issues = sum(bool(item["issues"]) for item in items)
    return {
        "success": True,
        "os": platform.system(),
        "total_startup_programs": len(items),
        "actionable_startup_programs": actionable,
        "entries_with_issues": issues,
        "startup_programs": items,
        "errors": errors,
        "message": _summary_message(items, actionable, issues),
    }

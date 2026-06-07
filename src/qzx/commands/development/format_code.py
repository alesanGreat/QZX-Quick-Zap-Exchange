#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FormatCode Command - Auto-detects language and formats source code files
using the appropriate formatter (black, prettier, rustfmt, gofmt, php-cs-fixer, clang-format).
"""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase
from qzx.core.recursive_findfiles_utils import find_files


class FormatCodeCommand(CommandBase):
    """
    Command to format source code files by auto-detecting the language
    and invoking the matching formatter tool.
    """

    name = "formatCode"
    aliases = ["fmtCode", "codeFmt", "formatSource"]
    description = "Formats source code files by auto-detecting language and invoking the right formatter"
    category = "development"

    parameters = [
        {
            'name': 'path',
            'description': 'File or directory to format',
            'required': True
        },
        {
            'name': 'language',
            'description': 'Force a specific language (python, javascript, typescript, rust, go, php, c, cpp). Auto-detected by default.',
            'required': False,
            'default': ''
        },
        {
            'name': 'dry_run',
            'description': 'Check if files would be changed without writing (true/false)',
            'required': False,
            'default': 'false'
        }
    ]

    examples = [
        {
            'command': 'qzx formatCode src/',
            'description': 'Format all supported source files in src/'
        },
        {
            'command': 'qzx formatCode src/main.py',
            'description': 'Format a single Python file with black'
        },
        {
            'command': 'qzx formatCode src/ python',
            'description': 'Format only Python files in src/'
        },
        {
            'command': 'qzx formatCode src/ "" true',
            'description': 'Dry-run format to see which files would change'
        }
    ]

    # Mapping of language -> file extensions and formatter configuration
    FORMATTERS = {
        'python': {
            'extensions': {'.py'},
            'tool': 'black',
            'args': ['black'],
            'check_args': ['black', '--check'],
            'fallback': None,
        },
        'javascript': {
            'extensions': {'.js', '.jsx', '.mjs', '.cjs'},
            'tool': 'prettier',
            'args': ['npx', 'prettier', '--write'],
            'check_args': ['npx', 'prettier', '--check'],
            'fallback': None,
        },
        'typescript': {
            'extensions': {'.ts', '.tsx'},
            'tool': 'prettier',
            'args': ['npx', 'prettier', '--write'],
            'check_args': ['npx', 'prettier', '--check'],
            'fallback': None,
        },
        'rust': {
            'extensions': {'.rs'},
            'tool': 'rustfmt',
            'args': ['rustfmt'],
            'check_args': ['rustfmt', '--check'],
            'fallback': None,
        },
        'go': {
            'extensions': {'.go'},
            'tool': 'gofmt',
            'args': ['gofmt', '-w'],
            'check_args': ['gofmt', '-l'],
            'fallback': None,
        },
        'php': {
            'extensions': {'.php'},
            'tool': 'php-cs-fixer',
            'args': ['php-cs-fixer', 'fix'],
            'check_args': ['php-cs-fixer', 'fix', '--dry-run', '--diff'],
            'fallback': None,
        },
        'c': {
            'extensions': {'.c', '.h'},
            'tool': 'clang-format',
            'args': ['clang-format', '-i'],
            'check_args': ['clang-format', '--dry-run', '--Werror'],
            'fallback': None,
        },
        'cpp': {
            'extensions': {'.cpp', '.hpp', '.cc', '.cxx'},
            'tool': 'clang-format',
            'args': ['clang-format', '-i'],
            'check_args': ['clang-format', '--dry-run', '--Werror'],
            'fallback': None,
        },
    }

    EXTENSION_TO_LANGUAGE = {}
    for lang, cfg in FORMATTERS.items():
        for ext in cfg['extensions']:
            EXTENSION_TO_LANGUAGE[ext] = lang

    def execute(self, path, language='', dry_run='false'):
        """
        Formats source code files by auto-detecting language and invoking the appropriate formatter.

        Args:
            path (str): File or directory to format
            language (str): Optional language override
            dry_run (str): If 'true', only check without writing changes

        Returns:
            dict: Result summary
        """
        if isinstance(dry_run, str):
            dry_run = dry_run.lower() in ('true', 'yes', 'y', '1', 't')

        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return {
                "success": False,
                "error": f"Path '{path}' does not exist.",
                "message": f"Path '{path}' does not exist."
            }

        language = language.lower().strip() if isinstance(language, str) else ''
        if language and language not in self.FORMATTERS:
            return {
                "success": False,
                "error": f"Unsupported language: {language}",
                "message": f"Unsupported language '{language}'. Supported: {', '.join(sorted(self.FORMATTERS.keys()))}"
            }

        # Collect files to process
        files_to_process = []
        if os.path.isfile(abs_path):
            ext = os.path.splitext(abs_path)[1].lower()
            detected = self.EXTENSION_TO_LANGUAGE.get(ext)
            if not detected:
                return {
                    "success": False,
                    "error": f"Unsupported file type: {ext}",
                    "message": f"File extension '{ext}' is not supported by formatCode."
                }
            if language and language != detected:
                return {
                    "success": False,
                    "error": f"Language mismatch: requested '{language}' but file is '{detected}'",
                    "message": f"The provided language '{language}' does not match the auto-detected language '{detected}'."
                }
            files_to_process.append((abs_path, detected))
        else:
            # Directory: collect all supported files
            target_langs = {language} if language else set(self.FORMATTERS.keys())
            for file_path in find_files(abs_path, recursive=True, file_type='f'):
                ext = os.path.splitext(file_path)[1].lower()
                detected = self.EXTENSION_TO_LANGUAGE.get(ext)
                if detected and detected in target_langs:
                    files_to_process.append((file_path, detected))

        if not files_to_process:
            return {
                "success": True,
                "path": abs_path,
                "dry_run": dry_run,
                "total_files": 0,
                "formatted_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "formatted": [],
                "skipped": [],
                "failed": [],
                "unavailable_tools": [],
                "message": "No supported source files found to format."
            }

        # Group by language
        by_language = {}
        for file_path, lang in files_to_process:
            by_language.setdefault(lang, []).append(file_path)

        formatted = []
        failed = []
        skipped = []
        unavailable_tools = []

        for lang, file_list in by_language.items():
            cfg = self.FORMATTERS[lang]
            tool = cfg['tool']

            if not self._is_tool_available(tool):
                unavailable_tools.append(tool)
                for f in file_list:
                    failed.append({
                        "file": f,
                        "language": lang,
                        "reason": f"Formatter '{tool}' is not installed or not on PATH."
                    })
                continue

            base_args = cfg['check_args'] if dry_run else cfg['args']

            for file_path in file_list:
                result = self._run_formatter(base_args, file_path, dry_run)
                if result["ok"]:
                    if dry_run and not result.get("would_change", True):
                        skipped.append({
                            "file": file_path,
                            "language": lang,
                            "note": "Already formatted"
                        })
                    else:
                        formatted.append({
                            "file": file_path,
                            "language": lang,
                            "dry_run": dry_run
                        })
                else:
                    failed.append({
                        "file": file_path,
                        "language": lang,
                        "reason": result.get("error", "Unknown error")
                    })

        # Build verbose message
        action = "checked" if dry_run else "formatted"
        msg = f"FormatCode Report ({action} mode):\n"
        msg += f"- Total files scanned: {len(files_to_process)}\n"
        msg += f"- Successfully {action}: {len(formatted)}\n"
        if dry_run:
            msg += f"- Already formatted (no changes needed): {len(skipped)}\n"
        msg += f"- Failed: {len(failed)}\n"

        if unavailable_tools:
            msg += f"\n⚠️  Missing formatters (not on PATH): {', '.join(sorted(set(unavailable_tools)))}\n"

        if failed:
            msg += "\n❌ Failures:\n"
            for item in failed[:10]:
                msg += f"  - {item['file']} ({item['language']}): {item['reason']}\n"
            if len(failed) > 10:
                msg += f"  ... and {len(failed) - 10} more failures.\n"

        if formatted:
            msg += f"\n✅ Successfully {action} files:\n"
            for item in formatted[:10]:
                msg += f"  - {item['file']} ({item['language']})\n"
            if len(formatted) > 10:
                msg += f"  ... and {len(formatted) - 10} more.\n"

        if not formatted and not failed and not skipped:
            msg += "\nℹ️ No action was taken."

        return {
            "success": True,
            "all_succeeded": len(failed) == 0,
            "path": abs_path,
            "dry_run": dry_run,
            "total_files": len(files_to_process),
            "formatted_count": len(formatted),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
            "formatted": formatted,
            "skipped": skipped,
            "failed": failed,
            "unavailable_tools": sorted(set(unavailable_tools)),
            "message": msg
        }

    def _is_tool_available(self, tool):
        """Check if a command-line tool is available on PATH."""
        try:
            subprocess.run(
                [tool, "--version"] if tool != 'php-cs-fixer' else [tool, '--version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            return True
        except FileNotFoundError:
            return False

    def _run_formatter(self, args, file_path, dry_run):
        """Run formatter command on a single file and return result dict."""
        try:
            cmd = args + [file_path]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            # gofmt -l returns the file path if it would change
            if dry_run and 'gofmt' in cmd[0]:
                would_change = file_path in result.stdout.strip()
                return {
                    "ok": True,
                    "would_change": would_change,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }

            # black --check exits 0 if already formatted, 1 if would change
            if dry_run and 'black' in cmd[0]:
                return {
                    "ok": True,
                    "would_change": result.returncode != 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }

            # prettier --check exits 0 if formatted, 1 if would change
            if dry_run and 'prettier' in cmd[0]:
                return {
                    "ok": True,
                    "would_change": result.returncode != 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }

            # Generic dry-run handling
            if dry_run:
                return {
                    "ok": True,
                    "would_change": result.returncode != 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }

            # Non-dry-run: 0 is success
            if result.returncode == 0:
                return {"ok": True}

            return {
                "ok": False,
                "error": result.stderr.strip() or f"Exit code {result.returncode}"
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}

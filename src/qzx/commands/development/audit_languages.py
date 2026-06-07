#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AuditLanguages Command - Scans a project directory, identifies programming languages
present, and audits whether any active languages are underrepresented in QZX's toolset.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase
from qzx.core.recursive_findfiles_utils import find_files

class AuditLanguagesCommand(CommandBase):
    """
    Command to audit underrepresented programming languages in a project and trigger alerts.
    """
    
    name = "auditLanguages"
    description = "Audits a project workspace for programming languages and alerts on underrepresented ones in QZX"
    category = "development"
    
    parameters = [
        {
            'name': 'scan_path',
            'description': 'Path to scan for programming language files (defaults to current directory)',
            'required': False,
            'default': '.'
        },
        {
            'name': 'threshold',
            'description': 'Minimum file count threshold to analyze a language (default is 3)',
            'required': False,
            'default': 3
        }
    ]
    
    examples = [
        {
            'command': 'qzx auditLanguages',
            'description': 'Audit languages in the current directory'
        },
        {
            'command': 'qzx auditLanguages "src/" 5',
            'description': 'Audit languages in the src/ directory with a minimum file count of 5'
        }
    ]

    # QZX capabilities matrix for languages
    QZX_CAPABILITIES = {
        'python': {
            'display_name': 'Python',
            'scaffolding': True,
            'complexity': True,
            'dead_code': True,
            'env_fallbacks': True
        },
        'javascript': {
            'display_name': 'JavaScript',
            'scaffolding': True,
            'complexity': True,
            'dead_code': True,
            'env_fallbacks': True
        },
        'typescript': {
            'display_name': 'TypeScript',
            'scaffolding': True,
            'complexity': True,
            'dead_code': True,
            'env_fallbacks': True
        },
        'php': {
            'display_name': 'PHP',
            'scaffolding': True,
            'complexity': True,
            'dead_code': True,
            'env_fallbacks': True
        },
        'rust': {
            'display_name': 'Rust',
            'scaffolding': True,
            'complexity': True,
            'dead_code': True,
            'env_fallbacks': True
        },
        'go': {
            'display_name': 'Go',
            'scaffolding': False,
            'complexity': True,
            'dead_code': False,
            'env_fallbacks': False
        },
        'java': {
            'display_name': 'Java',
            'scaffolding': False,
            'complexity': True,
            'dead_code': False,
            'env_fallbacks': False
        },
        'ruby': {
            'display_name': 'Ruby',
            'scaffolding': False,
            'complexity': True,
            'dead_code': False,
            'env_fallbacks': False
        },
        'c': {
            'display_name': 'C',
            'scaffolding': True,
            'complexity': True,
            'dead_code': False,
            'env_fallbacks': False
        },
        'cpp': {
            'display_name': 'C++',
            'scaffolding': True,
            'complexity': True,
            'dead_code': True,
            'env_fallbacks': True
        },
        'csharp': {
            'display_name': 'C#',
            'scaffolding': False,
            'complexity': True,
            'dead_code': False,
            'env_fallbacks': False
        }
    }

    EXTENSION_TO_LANGUAGE = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.php': 'php',
        '.rs': 'rust',
        '.go': 'go',
        '.java': 'java',
        '.rb': 'ruby',
        '.c': 'c',
        '.cpp': 'cpp',
        '.h': 'c',
        '.hpp': 'cpp',
        '.cs': 'csharp'
    }

    def execute(self, scan_path='.', threshold=3):
        """
        Executes the language representation audit
        
        Args:
            scan_path (str): Path to scan
            threshold (int/str): Minimum file count to trigger audits
            
        Returns:
            Dictionary containing audit details and warnings
        """
        abs_scan_path = os.path.abspath(scan_path)
        if not os.path.exists(abs_scan_path):
            return {
                "success": False,
                "error": f"Path '{scan_path}' does not exist.",
                "message": f"Path '{scan_path}' does not exist."
            }
            
        try:
            threshold = int(threshold)
        except (ValueError, TypeError):
            threshold = 3
            
        # 1. Count file extensions in the target path
        language_file_counts = {}
        total_relevant_files = 0
        
        # Discover all files recursively
        if os.path.isdir(abs_scan_path):
            for file_path in find_files(abs_scan_path, recursive=True, file_type='f'):
                _, ext = os.path.splitext(file_path)
                ext = ext.lower()
                if ext in self.EXTENSION_TO_LANGUAGE:
                    lang = self.EXTENSION_TO_LANGUAGE[ext]
                    language_file_counts[lang] = language_file_counts.get(lang, 0) + 1
                    total_relevant_files += 1
        elif os.path.isfile(abs_scan_path):
            _, ext = os.path.splitext(abs_scan_path)
            ext = ext.lower()
            if ext in self.EXTENSION_TO_LANGUAGE:
                lang = self.EXTENSION_TO_LANGUAGE[ext]
                language_file_counts[lang] = 1
                total_relevant_files = 1
                
        # 2. Audit each detected language
        alerts = []
        fully_represented = []
        partially_represented = []
        
        for lang, count in language_file_counts.items():
            if count < threshold:
                continue
                
            caps = self.QZX_CAPABILITIES.get(lang)
            if not caps:
                # Completely unknown / unsupported language
                alerts.append({
                    "language": lang,
                    "display_name": lang.capitalize(),
                    "file_count": count,
                    "percentage": round((count / total_relevant_files) * 100, 1) if total_relevant_files > 0 else 0,
                    "severity": "CRITICAL",
                    "reason": "Language is completely unsupported in QZX core capabilities.",
                    "missing_capabilities": ["scaffolding", "complexity", "dead_code", "env_fallbacks"]
                })
                continue
                
            # Compute support score
            supported_caps = []
            missing_caps = []
            
            for key in ['scaffolding', 'complexity', 'dead_code', 'env_fallbacks']:
                if caps[key]:
                    supported_caps.append(key)
                else:
                    missing_caps.append(key)
                    
            pct = round((count / total_relevant_files) * 100, 1) if total_relevant_files > 0 else 0
            
            # Severity criteria
            if len(supported_caps) == 4:
                fully_represented.append({
                    "language": lang,
                    "display_name": caps["display_name"],
                    "file_count": count,
                    "percentage": pct
                })
            elif len(supported_caps) <= 1:
                alerts.append({
                    "language": lang,
                    "display_name": caps["display_name"],
                    "file_count": count,
                    "percentage": pct,
                    "severity": "HIGH",
                    "reason": f"Language has high presence ({count} files, {pct}%) but has minimal support in QZX ({len(supported_caps)}/4 capabilities).",
                    "missing_capabilities": missing_caps
                })
            else:
                partially_represented.append({
                    "language": lang,
                    "display_name": caps["display_name"],
                    "file_count": count,
                    "percentage": pct,
                    "supported_capabilities": supported_caps,
                    "missing_capabilities": missing_caps
                })
                # If a partially represented language represents a significant percentage, trigger warning alert
                if pct >= 15.0 and len(missing_caps) > 0:
                    alerts.append({
                        "language": lang,
                        "display_name": caps["display_name"],
                        "file_count": count,
                        "percentage": pct,
                        "severity": "WARNING",
                        "reason": f"Language has moderate presence ({count} files, {pct}%) but is missing some QZX tools.",
                        "missing_capabilities": missing_caps
                    })
                    
        # 3. Formulate output message (Verbose is Gold)
        msg = f"QZX Language Representation Audit Report:\n"
        msg += f"- Scanned Path: {abs_scan_path}\n"
        msg += f"- Total code files matched: {total_relevant_files}\n"
        msg += f"- Minimum file threshold: {threshold}\n\n"
        
        if language_file_counts:
            msg += "Detected Languages Profile:\n"
            for lang, count in sorted(language_file_counts.items(), key=lambda x: x[1], reverse=True):
                pct = round((count / total_relevant_files) * 100, 1) if total_relevant_files > 0 else 0
                display = self.QZX_CAPABILITIES.get(lang, {}).get("display_name", lang.capitalize())
                msg += f"  - {display}: {count} files ({pct}%)\n"
        else:
            msg += "No supported programming language files detected in the scanned path.\n"
            
        # Append alerts
        if alerts:
            msg += "\n⚠️  ALERTS FOR SUBREPRESENTED LANGUAGES:\n"
            for idx, alert in enumerate(alerts, 1):
                msg += f"  {idx}. [{alert['severity']}] {alert['display_name']} ({alert['file_count']} files, {alert['percentage']}%):\n"
                msg += f"     Reason: {alert['reason']}\n"
                msg += f"     Missing in QZX: {', '.join(alert['missing_capabilities'])}\n"
        else:
            msg += "\n✅ All active languages in this project are fully supported in QZX.\n"
            
        return {
            "success": True,
            "scan_path": abs_scan_path,
            "total_files": total_relevant_files,
            "languages_found": language_file_counts,
            "alerts_count": len(alerts),
            "alerts": alerts,
            "fully_represented": fully_represented,
            "partially_represented": partially_represented,
            "message": msg
        }

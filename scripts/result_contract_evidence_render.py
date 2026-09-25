"""Render QZX Result Contract evidence receipts for CLI output."""

from __future__ import annotations

import sys


def render_receipt(report, args, serialized):
    """Render a conformance receipt as JSON or human-readable text."""
    if args.json:
        sys.stdout.write(serialized)
        return
    prefix = "[OK]" if report["success"] else "[FAIL]"
    print(f"{prefix} {report['message']}")
    print(f"  Profile: {report['details']['profile']}")
    for case in report["details"]["cases"]:
        _render_case(case)
    for violation in report["details"]["violations"]:
        print(f"  - {violation}")
    for warning in report["warnings"]:
        print(f"  [WARN] {warning}")
    if args.report:
        print(f"  Receipt: {args.report}")


def _render_case(case):
    marker = "OK" if case["conformant"] else "FAIL"
    print(f"  [{marker}] {case['name']}: {case['file']}")
    for violation in case["violations"]:
        print(f"    - {violation}")
    for warning in case["warnings"]:
        print(f"    [WARN] {warning}")

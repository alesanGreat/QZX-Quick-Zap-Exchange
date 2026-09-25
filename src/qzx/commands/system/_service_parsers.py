"""Native service-manager parsers for listSystemServices."""

from __future__ import annotations

import re


def parse_openrc_status(stdout):
    services = []
    pattern = re.compile(
        r"^\s*([A-Za-z0-9_.@:+-]+)\s+\[\s*([A-Za-z]+)\s*\]"
    )
    for line in stdout.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        name, state = match.groups()
        services.append(
            {
                "name": name,
                "display_name": name,
                "status": (
                    "running"
                    if state.lower() in {"started", "starting"}
                    else "stopped"
                ),
            }
        )
    return services


def parse_sc_query(stdout):
    services = []
    current = None
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if line.startswith("SERVICE_NAME:"):
            current = line.split(":", 1)[1].strip()
            continue
        if current and line.startswith("STATE"):
            state = line.split(":", 1)[1]
            services.append(
                {
                    "name": current,
                    "display_name": current,
                    "status": "running" if "RUNNING" in state else "stopped",
                }
            )
            current = None
    return services

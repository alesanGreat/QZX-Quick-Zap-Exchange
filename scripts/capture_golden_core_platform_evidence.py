#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Capture sanitized, reviewable Golden Core evidence on one real CI host."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.golden_core_platform_assertions import (  # noqa: E402
    command_assertions,
)
from scripts.golden_core_platform_capture_flow import (  # noqa: E402
    capture_platform_evidence,
)
from scripts.golden_core_platform_common import (  # noqa: E402
    canonical_json_bytes,
    environment_facts,
    path_variants,
    replacement_pairs as _replacement_pairs,
    sanitize_text,
    sanitize_value,
    sha256_value,
    source_revision as _source_revision,
)
from scripts.golden_core_platform_execution import run_qzx  # noqa: E402
from scripts.golden_core_platform_fixtures import (  # noqa: E402
    create_fixtures,
    run_git,
)


__all__ = [
    "canonical_json_bytes",
    "capture",
    "command_assertions",
    "create_fixtures",
    "environment_facts",
    "path_variants",
    "replacement_pairs",
    "run_git",
    "run_qzx",
    "sanitize_text",
    "sanitize_value",
    "sha256_value",
    "source_revision",
]


SCHEMA_VERSION = 2
EXPECTED_COMMAND_COUNT = 15


class EvidenceHttpHandler(BaseHTTPRequestHandler):
    """Serve one deterministic, authorized loopback response."""

    protocol_version = "HTTP/1.1"
    server_version = "QZX-platform-evidence"
    sys_version = ""

    def date_time_string(self, _timestamp=None):
        return "Sat, 08 Aug 2026 00:00:00 GMT"

    def do_GET(self):
        body = b"qzx-platform-evidence"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        return


@contextmanager
def local_http_server():
    """Yield an HTTP URL bound only to the local loopback interface."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), EvidenceHttpHandler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/ok"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        if thread.is_alive():
            raise RuntimeError("The platform-evidence HTTP server did not stop.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination JSON file for this one-host evidence record.",
    )
    parser.add_argument(
        "--environment-id",
        required=True,
        help="Stable matrix environment identifier.",
    )
    parser.add_argument(
        "--environment-name",
        required=True,
        help="Human-readable matrix environment name.",
    )
    return parser.parse_args()


def source_revision() -> str:
    return _source_revision(PROJECT_ROOT)


def replacement_pairs(fixture_root: Path) -> list[tuple[str, str]]:
    return _replacement_pairs(fixture_root, PROJECT_ROOT)


def capture(environment_id: str, environment_name: str) -> dict[str, Any]:
    return capture_platform_evidence(
        environment_id,
        environment_name,
        local_http_server=local_http_server,
    )


def main() -> int:
    arguments = parse_args()
    document = capture(arguments.environment_id, arguments.environment_name)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(
        (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode(
            "utf-8"
        )
    )
    print(
        "Captured {} Golden Core commands on {} ({}).".format(
            document["summary"]["passed"],
            document["environment"]["name"],
            document["environment"]["system"],
        )
    )
    print("Evidence SHA-256: {}".format(document["evidence_sha256"]))
    print("Output: {}".format(arguments.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

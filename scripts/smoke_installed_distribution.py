#!/usr/bin/env python
"""Install one built QZX wheel in isolation and exercise its real CLI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def _venv_python(environment_root: Path) -> Path:
    if os.name == "nt":
        return environment_root / "Scripts" / "python.exe"
    return environment_root / "bin" / "python"


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _subprocess_environment(
    source: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return a deterministic Python environment without ambient import paths."""
    environment = dict(os.environ if source is None else source)
    for variable in (
        "PYTHONHOME",
        "PYTHONINSPECT",
        "PYTHONPATH",
        "PYTHONSTARTUP",
    ):
        environment.pop(variable, None)
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "QZX_TELEMETRY": "0",
        }
    )
    return environment


def _run_checked(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=_subprocess_environment(),
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Command failed with exit code {}:\n{}\nstdout:\n{}\nstderr:\n{}".format(
                completed.returncode,
                " ".join(command),
                completed.stdout,
                completed.stderr,
            )
        )
    return completed


def _invoke_qzx_json(
    arguments: list[str],
    *,
    cwd: Path,
    runner=None,
) -> dict:
    run = _run_checked if runner is None else runner
    completed = run(
        [sys.executable, "-I", "-B", "-m", "qzx", *arguments, "--json"],
        cwd=cwd,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "QZX did not emit exactly one JSON document for {!r}:\n{}".format(
                arguments,
                completed.stdout,
            )
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"QZX JSON payload is not an object: {payload!r}")
    return payload


def _require(condition: bool, message: str, payload: dict | None = None) -> None:
    if condition:
        return
    suffix = "" if payload is None else "\npayload=" + json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    raise RuntimeError(message + suffix)


def _smoke_installed_environment(expected_prefix: Path) -> dict:
    import qzx

    package_file = Path(qzx.__file__).resolve()
    _require(
        _is_within(package_file, expected_prefix),
        f"QZX imported from {package_file}, outside installed prefix {expected_prefix}",
    )

    with tempfile.TemporaryDirectory(prefix="qzx-installed-cli-") as temporary:
        root = Path(temporary)
        (root / "image.txt").write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 512
        )
        (root / "utf16.txt").write_bytes(
            "one\r\ntwo\n".encode("utf-16")
        )
        hidden_only = root / "hidden-only"
        hidden_only.mkdir()
        (hidden_only / ".secret").write_text("hidden", encoding="utf-8")

        detected = _invoke_qzx_json(
            ["detectFileType", "image.txt", "true"],
            cwd=root,
        )
        _require(
            detected.get("success") is True
            and detected.get("mime_type") == "image/png"
            and detected.get("suggested_extension") == ".png",
            "detectFileType installed-wheel smoke failed",
            detected,
        )

        binary = _invoke_qzx_json(
            ["isFileBinary", "utf16.txt", "1024", "10"],
            cwd=root,
        )
        _require(
            binary.get("success") is True and binary.get("is_binary") is False,
            "isFileBinary installed-wheel smoke failed",
            binary,
        )

        empty_file = _invoke_qzx_json(
            ["isFileEmpty", "utf16.txt", "true"],
            cwd=root,
        )
        _require(
            empty_file.get("success") is True
            and empty_file.get("is_empty") is False,
            "isFileEmpty installed-wheel smoke failed",
            empty_file,
        )

        lines = _invoke_qzx_json(["countLines", "utf16.txt"], cwd=root)
        _require(
            lines.get("success") is True
            and lines.get("line_count") == 2
            and lines.get("encoding") == "utf-16-le",
            "countLines installed-wheel smoke failed",
            lines,
        )

        empty_directory = _invoke_qzx_json(
            ["isDirectoryEmpty", "hidden-only"],
            cwd=root,
        )
        _require(
            empty_directory.get("success") is True
            and empty_directory.get("is_empty") is True
            and empty_directory.get("details", {}).get(
                "ignored_hidden_entries"
            )
            == 1,
            "isDirectoryEmpty installed-wheel smoke failed",
            empty_directory,
        )

        created = _invoke_qzx_json(
            ["createDirectory", "created/a/b"],
            cwd=root,
        )
        _require(
            created.get("success") is True
            and (root / "created" / "a" / "b").is_dir(),
            "createDirectory installed-wheel smoke failed",
            created,
        )

        tree = _invoke_qzx_json(
            ["getProjectTree", "created", "3"],
            cwd=root,
        )
        _require(
            tree.get("success") is True
            and tree.get("details", {}).get("entry_count", 0) >= 2
            and tree.get("details", {}).get("symbolic_links_followed") is False,
            "getProjectTree installed-wheel smoke failed",
            tree,
        )

        cleared = _invoke_qzx_json(["clearScreen"], cwd=root)
        _require(
            cleared.get("success") is True
            and cleared.get("screen_cleared") is False
            and cleared.get("details", {}).get("reason")
            == "non_interactive_output",
            "clearScreen installed-wheel smoke failed",
            cleared,
        )

    return {
        "success": True,
        "package_file": str(package_file),
        "python_executable": sys.executable,
        "checks": {
            "detect_file_type": detected["mime_type"],
            "utf16_binary": binary["is_binary"],
            "utf16_empty": empty_file["is_empty"],
            "utf16_line_count": lines["line_count"],
            "hidden_only_directory_empty": empty_directory["is_empty"],
            "nested_directory_created": True,
            "project_tree_entry_count": tree["details"]["entry_count"],
            "redirected_screen_cleared": cleared["screen_cleared"],
        },
    }


def _find_one_wheel(dist_dir: Path) -> Path:
    wheels = sorted(dist_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(
            f"Expected exactly one wheel in {dist_dir}, found {len(wheels)}."
        )
    return wheels[0].resolve()


def _install_and_smoke(dist_dir: Path) -> dict:
    wheel = _find_one_wheel(dist_dir)
    script = Path(__file__).resolve()
    with tempfile.TemporaryDirectory(prefix="qzx-wheel-environment-") as temporary:
        environment_root = Path(temporary) / "venv"
        venv.EnvBuilder(
            with_pip=True,
            clear=True,
            system_site_packages=True,
        ).create(environment_root)
        python = _venv_python(environment_root)
        _run_checked(
            [
                str(python),
                "-I",
                "-B",
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-deps",
                "--force-reinstall",
                str(wheel),
            ]
        )
        completed = _run_checked(
            [
                str(python),
                "-B",
                str(script),
                "--inside-installed-environment",
                "--expected-prefix",
                str(environment_root),
            ],
            cwd=environment_root,
        )
        try:
            inner = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Installed-environment smoke did not emit JSON:\n"
                + completed.stdout
            ) from exc
    return {
        "success": True,
        "wheel": str(wheel),
        "installed_environment": inner,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=Path("dist"),
        help="Directory containing exactly one built wheel",
    )
    parser.add_argument(
        "--inside-installed-environment",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--expected-prefix",
        type=Path,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.inside_installed_environment:
            if args.expected_prefix is None:
                raise RuntimeError("--expected-prefix is required in inner mode")
            result = _smoke_installed_environment(args.expected_prefix)
        else:
            result = _install_and_smoke(args.dist_dir.resolve())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

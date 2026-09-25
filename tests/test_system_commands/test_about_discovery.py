"""Intentional discovery from the terminal, without paywalls or side effects."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

from qzx.commands.system import about
from qzx.identity import product_identity, product_manifest


def test_about_retains_identity_and_adds_reachable_next_steps():
    result = about.AboutCommand().execute()
    manifest = product_manifest()
    assert result["success"] is True
    assert result["attribution"] == product_identity()["attribution"]
    assert result["author"]["name"] == manifest["product"]["author"]["name"]
    assert result["links"]["creator"] == manifest["product"]["author"]["profile_url"]
    assert result["links"]["repository"] == manifest["urls"]["repository"]
    assert result["links"]["documentation"] == manifest["urls"]["command_catalog"]
    for key in ("creator", "repository", "support", "professional_services"):
        assert result["links"][key] in result["message"]
    assert "optional" in result["message"]
    assert "no paid plans or paid features" in result["message"]
    assert "never unlock features or purchase priority" in result["message"]


def test_project_origin_and_author_come_from_the_manifest():
    manifest = copy.deepcopy(product_manifest())
    manifest["urls"].update(site_origin="https://qzx.example/", repository="https://code.example/qzx")
    manifest["product"]["author"]["profile_url"] = "https://qzx.example/creator"
    result = about.AboutCommand(
        manifest_provider=lambda: manifest
    ).execute()
    assert result["links"]["support"] == "https://qzx.example/en/donate"
    assert result["links"]["professional_services"] == "https://qzx.example/en/professional-services"
    assert result["links"]["creator"] == "https://qzx.example/creator"
    assert result["links"]["repository"] == "https://code.example/qzx"


def test_about_has_no_browser_process_or_network_boundary():
    assert "socket" not in about.__dict__
    assert "subprocess" not in about.__dict__
    assert "webbrowser" not in about.__dict__
    assert about.AboutCommand().execute()["success"] is True


def _cli(*arguments):
    source = Path(__file__).resolve().parents[2] / "src"
    env = dict(os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE="1", QZX_TELEMETRY="0", DO_NOT_TRACK="1", PYTHONUTF8="1")
    return subprocess.run(
        [sys.executable, "-B", "-m", "qzx", "about", *arguments], env=env,
        capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def test_about_real_json_cli_has_links_in_one_result():
    completed = _cli("--json")
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["success"] is True
    assert result["links"]["support"].endswith("/en/donate")
    assert result["links"]["professional_services"].endswith("/en/professional-services")


def test_about_real_human_cli_exposes_voluntary_support():
    completed = _cli()
    assert completed.returncode == 0, completed.stderr
    text = completed.stdout.decode("utf-8")
    assert "Alejandro Sánchez" in text
    assert "/en/donate" in text
    assert "/en/professional-services" in text
    assert "optional" in text

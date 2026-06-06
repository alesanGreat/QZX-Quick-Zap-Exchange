#!/usr/bin/env python3
"""
Build and deploy WebsiteQZX to its dedicated Incus container on Hetzner.

    5.161.246.120:2237 -> qzx (10.204.179.237):22
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEBSITE_DIR = PROJECT_ROOT / "WebsiteQZX"
DEFAULT_SOURCE = WEBSITE_DIR / "dist"

REMOTE_HOST = os.getenv("DEPLOY_SSH", "deploy@5.161.246.120")
REMOTE_PORT = int(os.getenv("DEPLOY_SSH_PORT", "2237"))
REMOTE_PATH = os.getenv("DEPLOY_PATH", "/var/www/html").rstrip("/") + "/"
HEALTH_URL = os.getenv("DEPLOY_HEALTH_URL", "https://qzx.yumbale.com/")
SIGNATURE_FILE = ".qzx-deploy-signature"

SERVER_TOOLS_DIR = Path(
    os.getenv(
        "QZX_SERVER_TOOLS_DIR",
        r"C:\Team Dropbox\Valis Idealis\Servidores VPSs y Equipos de Clientes\RelacionadoConServidores",
    )
)
DEFAULT_SOURCE_KEY = SERVER_TOOLS_DIR / "hetzner.ssh"
SAFE_KEY_PATH = Path.home() / ".ssh" / "qzx_hetzner.ssh"

RSYNC_CANDIDATES = [
    Path(r"C:\ProgramData\chocolatey\bin\rsync.exe"),
    Path(r"C:\ProgramData\chocolatey\lib\rsync\tools\bin\rsync.exe"),
]
SSH_CANDIDATES = [
    Path(r"C:\ProgramData\chocolatey\lib\rsync\tools\bin\ssh.exe"),
    Path("/mnt/c/ProgramData/chocolatey/lib/rsync/tools/bin/ssh.exe"),
]
CHOCOLATEY_SSH_SEGMENT = "chocolatey\\lib\\rsync\\tools\\bin\\ssh.exe"


def is_wsl() -> bool:
    try:
        release = Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8")
        return "microsoft" in release.lower()
    except OSError:
        return False


def uses_chocolatey_ssh(ssh_bin: str) -> bool:
    return CHOCOLATEY_SSH_SEGMENT in ssh_bin.lower().replace("/", "\\")


def to_cygwin_path(path: Path) -> str:
    posix_path = path.as_posix()
    if path.drive:
        drive = path.drive.rstrip(":").lower()
        return f"/cygdrive/{drive}{posix_path[2:]}"
    if posix_path.startswith("/mnt/") and len(posix_path) > 7:
        drive = posix_path[5].lower()
        if drive.isalpha() and posix_path[6] == "/":
            return f"/cygdrive/{drive}{posix_path[6:]}"
    return posix_path


def resolve_rsync() -> str:
    for candidate in RSYNC_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return shutil.which("rsync") or "rsync"


def resolve_ssh() -> str:
    for candidate in SSH_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return shutil.which("ssh") or "ssh"


def resolve_pnpm() -> str:
    return shutil.which("pnpm.cmd") or shutil.which("pnpm") or "pnpm"


def source_identity() -> Path | None:
    raw_key = (os.getenv("DEPLOY_SSH_KEY") or "").strip()
    if raw_key:
        candidate = Path(raw_key).expanduser()
        if candidate.exists():
            return candidate
    if DEFAULT_SOURCE_KEY.exists():
        return DEFAULT_SOURCE_KEY
    for candidate in [
        Path.home() / ".ssh" / "qzx_hetzner.ssh",
        Path.home() / ".ssh" / "id_ed25519",
        Path.home() / ".ssh" / "id_rsa",
    ]:
        if candidate.exists():
            return candidate
    return None


def tighten_windows_acl(path: Path) -> None:
    if os.name != "nt":
        return

    accounts: list[str] = []
    whoami = subprocess.run(
        ["whoami"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if whoami:
        accounts.append(whoami)

    user = os.getenv("USERNAME")
    domain = os.getenv("USERDOMAIN")
    if domain and user:
        accounts.append(f"{domain}\\{user}")
    if user:
        accounts.append(user)

    subprocess.run(
        ["icacls", str(path), "/inheritance:r"],
        check=False,
        capture_output=True,
        text=True,
    )
    for account in dict.fromkeys(accounts):
        subprocess.run(
            ["icacls", str(path), "/grant:r", f"{account}:F"],
            check=False,
            capture_output=True,
            text=True,
        )


def prepare_identity() -> Path | None:
    source = source_identity()
    if source is None:
        return None

    if os.name == "nt":
        SAFE_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        old_data = SAFE_KEY_PATH.read_bytes() if SAFE_KEY_PATH.exists() else None
        new_data = source.read_bytes()
        if old_data != new_data:
            shutil.copyfile(source, SAFE_KEY_PATH)
        tighten_windows_acl(SAFE_KEY_PATH)
        return SAFE_KEY_PATH

    try:
        source.chmod(0o600)
    except OSError:
        pass
    return source


def identity_for_ssh(identity: Path, ssh_bin: str) -> str:
    if uses_chocolatey_ssh(ssh_bin):
        if is_wsl():
            return to_cygwin_path(identity)
        return identity.as_posix()
    return str(identity)


def known_hosts_for_ssh(ssh_bin: str) -> str:
    known_hosts = Path.home() / ".ssh" / "known_hosts"
    known_hosts.parent.mkdir(parents=True, exist_ok=True)
    known_hosts.touch(exist_ok=True)
    if uses_chocolatey_ssh(ssh_bin):
        if is_wsl():
            return to_cygwin_path(known_hosts)
        return known_hosts.as_posix()
    return str(known_hosts)


def local_path_for_rsync(path: Path, rsync_bin: str) -> str:
    normalized = rsync_bin.lower().replace("/", "\\")
    if path.drive and (
        os.name == "nt"
        or "chocolatey\\bin\\rsync.exe" in normalized
        or "chocolatey\\lib\\rsync" in normalized
    ):
        return to_cygwin_path(path)
    return str(path)


def install_and_build(skip_install: bool, skip_build: bool) -> bool:
    pnpm = resolve_pnpm()
    if not skip_install:
        install_cmd = [pnpm, "install"]
        if (WEBSITE_DIR / "pnpm-lock.yaml").exists():
            install_cmd.append("--frozen-lockfile")
        print(f"[INFO] Instalando dependencias con pnpm en {WEBSITE_DIR}")
        if subprocess.run(install_cmd, cwd=WEBSITE_DIR).returncode != 0:
            print("[FAIL] pnpm install fallo.")
            return False

    if not skip_build:
        print("[INFO] Compilando WebsiteQZX para deploy...")
        if subprocess.run([pnpm, "run", "build:deploy"], cwd=WEBSITE_DIR).returncode != 0:
            print("[FAIL] pnpm run build:deploy fallo.")
            return False

    return True


def assert_remote_signature(
    ssh_bin: str,
    identity: Path,
    known_hosts: str,
) -> bool:
    signature_path = f"{REMOTE_PATH}{SIGNATURE_FILE}"
    cmd = [
        ssh_bin,
        "-p",
        str(REMOTE_PORT),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        f"UserKnownHostsFile={known_hosts}",
        "-i",
        identity_for_ssh(identity, ssh_bin),
        REMOTE_HOST,
        f"test -f {signature_path}",
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        print(f"[FAIL] Falta la firma remota: {signature_path}")
        print("[ABORT] Se bloquea el deploy para evitar borrar una ruta equivocada.")
        return False
    return True


def build_rsync_command(
    source: Path,
    rsync_bin: str,
    ssh_bin: str,
    identity: Path,
    known_hosts: str,
    dry_run: bool,
) -> list[str]:
    ssh_transport = " ".join(
        [
            ssh_bin,
            "-p",
            str(REMOTE_PORT),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            f"UserKnownHostsFile={known_hosts}",
            "-i",
            identity_for_ssh(identity, ssh_bin),
        ]
    )
    cmd = [
        rsync_bin,
        "--recursive",
        "--links",
        "--times",
        "--checksum",
        "--no-perms",
        "--no-owner",
        "--no-group",
        "--chmod=Dug=rwx,Dgo=rx,Fug=rw,Fgo=r",
        "--compress",
        "--verbose",
        "--human-readable",
        "--itemize-changes",
        "--delete",
        f"--filter=protect {SIGNATURE_FILE}",
        f"--exclude={SIGNATURE_FILE}",
        "--exclude=.DS_Store",
        "--exclude=.htaccess",
        "--exclude=dist.zip",
        "-e",
        ssh_transport,
    ]
    if dry_run:
        cmd.append("--dry-run")
    cmd.extend(
        [
            local_path_for_rsync(source, rsync_bin).rstrip("/") + "/",
            f"{REMOTE_HOST}:{REMOTE_PATH}",
        ]
    )
    return cmd


def fetch_url(url: str) -> tuple[int, object, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "QZX deploy health check"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, response.headers, body
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, exc.headers, body


def validate_production() -> tuple[bool, str]:
    origin = HEALTH_URL.rstrip("/")
    root_status, _, root_body = fetch_url(f"{origin}/")
    if root_status != 200 or 'id="root"' not in root_body or "QZX" not in root_body:
        return False, f"home invalido: HTTP {root_status}"
    if 'href="https://qzx.yumbale.com/"' not in root_body or "qzx.dev" in root_body:
        return False, "canonical incorrecto en home"

    about_status, _, about_body = fetch_url(f"{origin}/about")
    if about_status != 200:
        return False, f"/about invalido: HTTP {about_status}"
    if 'href="https://qzx.yumbale.com/about"' not in about_body:
        return False, "canonical incorrecto en /about"
    if "About QZX and Its Cross-Platform Mission" not in about_body:
        return False, "head SEO especifico ausente en /about"

    robots_status, robots_headers, robots_body = fetch_url(f"{origin}/robots.txt")
    if robots_status != 200 or "text/plain" not in robots_headers.get_content_type():
        return False, f"robots.txt invalido: HTTP {robots_status}"
    if "Sitemap: https://qzx.yumbale.com/sitemap.xml" not in robots_body:
        return False, "robots.txt no anuncia el sitemap"

    sitemap_status, sitemap_headers, sitemap_body = fetch_url(f"{origin}/sitemap.xml")
    if sitemap_status != 200 or sitemap_headers.get_content_type() not in {
        "application/xml",
        "text/xml",
    }:
        return False, f"sitemap invalido: HTTP {sitemap_status}"
    try:
        sitemap_root = ET.fromstring(sitemap_body)
    except ET.ParseError as exc:
        return False, f"sitemap XML invalido: {exc}"

    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    sitemap_urls = {
        element.text
        for element in sitemap_root.findall("sm:url/sm:loc", namespace)
        if element.text
    }
    expected_urls = {
        f"{origin}/",
        f"{origin}/about",
        f"{origin}/commands",
        f"{origin}/contact",
        f"{origin}/why-qzx",
        f"{origin}/commands-doc",
        f"{origin}/donate",
        f"{origin}/qzx-in-action",
    }
    if sitemap_urls != expected_urls:
        return False, f"URLs inesperadas en sitemap: {sorted(sitemap_urls)}"
    if any("/admin" in url for url in sitemap_urls):
        return False, "el sitemap expone rutas admin"

    admin_status, admin_headers, _ = fetch_url(f"{origin}/admin")
    if admin_status != 200 or "noindex" not in admin_headers.get("X-Robots-Tag", ""):
        return False, "admin no esta protegido con X-Robots-Tag"

    missing_status, _, _ = fetch_url(f"{origin}/seo-healthcheck-not-found")
    if missing_status != 404:
        return False, f"ruta inexistente no devuelve 404: HTTP {missing_status}"

    return True, "home, canonicals, robots, sitemap, admin y 404 validos"


def health_check(attempts: int = 5, wait_seconds: int = 2) -> bool:
    print(f"[INFO] Health checks SEO/HTTP: {HEALTH_URL}")
    for attempt in range(1, attempts + 1):
        try:
            valid, detail = validate_production()
            print(f"  Intento {attempt}/{attempts}: {detail}")
            if valid:
                return True
        except Exception as exc:
            print(f"  Intento {attempt}/{attempts}: {exc}")
        time.sleep(wait_seconds)
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build y deploy de WebsiteQZX al Incus qzx en Hetzner"
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="Directorio local a sincronizar (default: WebsiteQZX/dist)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Muestra cambios sin subir ni borrar")
    parser.add_argument("--skip-install", action="store_true", help="Omite pnpm install")
    parser.add_argument("--skip-build", action="store_true", help="Omite pnpm run build")
    parser.add_argument("--skip-health", action="store_true", help="Omite el health check HTTPS")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    if not install_and_build(args.skip_install, args.skip_build):
        return 1

    source = Path(args.source).resolve()
    if not source.is_dir() or not (source / "index.html").is_file():
        print(f"[FAIL] No existe un build valido en: {source}")
        return 1

    identity = prepare_identity()
    if identity is None:
        print("[FAIL] No se encontro la llave SSH de Hetzner.")
        return 1

    rsync_bin = resolve_rsync()
    ssh_bin = resolve_ssh()
    known_hosts = known_hosts_for_ssh(ssh_bin)

    print(f"[INFO] Source: {source}")
    print(f"[INFO] Destino: {REMOTE_HOST}:{REMOTE_PORT}{REMOTE_PATH}")
    print(f"[INFO] Llave SSH: {identity}")

    if not assert_remote_signature(ssh_bin, identity, known_hosts):
        return 44
    print(f"[OK] Firma remota encontrada: {REMOTE_PATH}{SIGNATURE_FILE}")

    cmd = build_rsync_command(
        source,
        rsync_bin,
        ssh_bin,
        identity,
        known_hosts,
        args.dry_run,
    )
    print("[INFO] Ejecutando rsync" + (" (dry-run)..." if args.dry_run else "..."))
    env = os.environ.copy()
    env.setdefault("HOME", str(Path.home()))
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        print(f"[FAIL] rsync termino con codigo {result.returncode}.")
        return result.returncode

    if not args.dry_run and not args.skip_health and not health_check():
        print("[FAIL] El sitio no supero el health check.")
        return 99

    print("[OK] Deploy QZX completado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

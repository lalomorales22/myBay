"""
ngrok tunnel management for myBay.

Used to automatically expose the local camera server so eBay can fetch images.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx


@dataclass
class NgrokStartResult:
    """Result of attempting to ensure a running ngrok tunnel."""

    running: bool
    public_url: Optional[str] = None
    started_by_app: bool = False
    error: Optional[str] = None


_managed_process: Optional[subprocess.Popen] = None


def _resource_dir() -> Path:
    """
    Resolve runtime resource directory.

    - Source mode: project root
    - Bundled mode (.app): Contents/Resources
    """
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()
        contents_dir = exe_path.parent.parent
        resources = contents_dir / "Resources"
        if resources.exists():
            return resources

        # Fallback for other PyInstaller layouts.
        maybe_meipass = getattr(sys, "_MEIPASS", None)
        if maybe_meipass:
            return Path(maybe_meipass)

    return Path(__file__).parent.parent


def _read_tunnels() -> list[dict]:
    """Read current ngrok tunnels from local ngrok API."""
    response = httpx.get("http://127.0.0.1:4040/api/tunnels", timeout=2.0)
    response.raise_for_status()
    payload = response.json() if response.content else {}
    tunnels = payload.get("tunnels", []) if isinstance(payload, dict) else []
    return tunnels if isinstance(tunnels, list) else []


def _is_port_match(addr: str, port: int) -> bool:
    if not addr:
        return False
    text = str(addr).strip()
    return text.endswith(f":{port}") or text == str(port)


def get_https_tunnel_url(port: int = 8000) -> Optional[str]:
    """Get active HTTPS ngrok tunnel URL for the given local port."""
    try:
        tunnels = _read_tunnels()
    except Exception:
        return None

    for tunnel in tunnels:
        if tunnel.get("proto") != "https":
            continue
        config = tunnel.get("config", {}) if isinstance(tunnel, dict) else {}
        addr = config.get("addr", "")
        if _is_port_match(addr, port):
            public_url = tunnel.get("public_url")
            if public_url:
                return str(public_url)

    # Fallback: first HTTPS tunnel if port metadata is unavailable.
    for tunnel in tunnels:
        if tunnel.get("proto") == "https" and tunnel.get("public_url"):
            return str(tunnel["public_url"])

    return None


def find_ngrok_binary() -> Optional[Path]:
    """Find ngrok binary from env, bundled resources, or system PATH."""
    env_path = os.getenv("NGROK_PATH")
    if env_path:
        path = Path(env_path).expanduser()
        if path.exists():
            return path

    resources = _resource_dir()
    bundled = resources / "ngrok"
    if bundled.exists():
        return bundled

    for candidate in ("ngrok", "/opt/homebrew/bin/ngrok", "/usr/local/bin/ngrok"):
        resolved = shutil.which(candidate) if candidate == "ngrok" else candidate
        if resolved and Path(resolved).exists():
            return Path(resolved)

    return None


def _ensure_executable(path: Path):
    """Ensure executable permission on ngrok binary."""
    try:
        mode = path.stat().st_mode
        path.chmod(mode | 0o111)
    except Exception:
        pass


def _configure_authtoken(ngrok_bin: Path):
    """
    Configure ngrok auth token if NGROK_AUTHTOKEN is provided.

    This is useful for fresh machines running packaged apps where ngrok has not
    been configured yet.
    """
    token = os.getenv("NGROK_AUTHTOKEN", "").strip()
    if not token:
        return

    try:
        subprocess.run(
            [str(ngrok_bin), "config", "add-authtoken", token],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        pass


def ensure_ngrok_tunnel(port: int = 8000, wait_seconds: float = 8.0) -> NgrokStartResult:
    """
    Ensure an ngrok HTTPS tunnel exists for the local server port.

    If a tunnel is already active, reuses it.
    Otherwise starts ngrok and waits briefly for tunnel registration.
    """
    global _managed_process

    existing = get_https_tunnel_url(port)
    if existing:
        return NgrokStartResult(
            running=True,
            public_url=existing,
            started_by_app=False,
        )

    ngrok_bin = find_ngrok_binary()
    if not ngrok_bin:
        return NgrokStartResult(
            running=False,
            error="ngrok binary not found (bundled or system PATH)",
        )

    _ensure_executable(ngrok_bin)
    _configure_authtoken(ngrok_bin)

    try:
        cmd = [str(ngrok_bin), "http", str(port)]
        # Use static domain if configured (free tier gets 1 static domain)
        static_domain = os.environ.get("NGROK_DOMAIN", "").strip()
        if static_domain:
            cmd = [str(ngrok_bin), "http", "--domain", static_domain, str(port)]
        _managed_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        return NgrokStartResult(running=False, error=f"failed to start ngrok: {e}")

    deadline = time.time() + max(1.0, wait_seconds)
    while time.time() < deadline:
        if _managed_process and _managed_process.poll() is not None:
            return NgrokStartResult(
                running=False,
                started_by_app=True,
                error=f"ngrok exited early with code {_managed_process.returncode}",
            )

        public_url = get_https_tunnel_url(port)
        if public_url:
            return NgrokStartResult(
                running=True,
                public_url=public_url,
                started_by_app=True,
            )

        time.sleep(0.35)

    return NgrokStartResult(
        running=True,
        started_by_app=True,
        error="ngrok started, but tunnel URL not ready yet",
    )


def stop_managed_ngrok():
    """Stop ngrok process started by this app process, if any."""
    global _managed_process
    proc = _managed_process
    _managed_process = None
    if not proc:
        return

    try:
        proc.terminate()
        proc.wait(timeout=3)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass

"""
odysseus_docker_setup.py — Auto-detect Docker and bring up Odysseus.

Verified against the actual odysseus-dev repo:
  - docker-compose.yml services: odysseus (port 7000), chromadb (8100),
    searxng (8080), ntfy (8091)
  - .env.example has the real config keys (LLM_HOST, OLLAMA_BASE_URL, etc.)
  - app.py exposes GET /api/health for readiness polling

What this does:
  1. Detects `docker` and `docker compose` (v2 plugin) on PATH.
  2. On Windows, also checks the Docker Desktop engine is actually running
     (docker info), since "docker.exe is on PATH" != "the daemon is up".
  3. Creates .env from .env.example if missing (never overwrites yours).
  4. Runs `docker compose up -d --build`.
  5. Polls http://127.0.0.1:7000/api/health until Odysseus responds, or
     times out with a clear diagnostic.

Run from the odysseus-dev root (same folder as docker-compose.yml):
    python3 odysseus_docker_setup.py
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error

REPO_MARKERS = ("docker-compose.yml", "Dockerfile", ".env.example")
HEALTH_URL = "http://127.0.0.1:7000/api/health"
APP_URL = "http://127.0.0.1:7000"


def step(msg: str) -> None:
    print(f"\n==> {msg}")


def fail(msg: str) -> None:
    print(f"\n[ERROR] {msg}")
    sys.exit(1)


def find_repo_root() -> str:
    """Confirm we're being run from (or under) the odysseus-dev folder."""
    cwd = os.getcwd()
    if all(os.path.exists(os.path.join(cwd, m)) for m in REPO_MARKERS):
        return cwd
    fail(
        "This doesn't look like the odysseus-dev folder "
        f"(missing one of {REPO_MARKERS}). "
        "Run this script from inside odysseus-dev/."
    )


def check_docker_installed() -> str:
    docker_path = shutil.which("docker")
    if not docker_path:
        fail(
            "Docker was not found on PATH.\n"
            "  Windows: install Docker Desktop (https://www.docker.com/products/docker-desktop/)\n"
            "           and make sure WSL2 backend is enabled during install.\n"
            "  macOS:   install Docker Desktop, same link.\n"
            "  Linux:   install docker-ce + the compose plugin via your package manager."
        )
    return docker_path


def check_docker_daemon_running() -> None:
    try:
        subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=15, check=True
        )
    except subprocess.CalledProcessError:
        fail(
            "Docker is installed but the daemon isn't responding.\n"
            "  Windows/macOS: open Docker Desktop and wait for it to say 'Engine running'.\n"
            "  Linux: check `sudo systemctl status docker`."
        )
    except FileNotFoundError:
        fail("docker command disappeared unexpectedly — reinstall Docker.")
    except subprocess.TimeoutExpired:
        fail("`docker info` timed out — Docker Desktop may still be starting. Wait and re-run.")


def check_compose_v2() -> None:
    try:
        result = subprocess.run(
            ["docker", "compose", "version"], capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
    except Exception:
        fail(
            "`docker compose` (v2, no hyphen) isn't available.\n"
            "  Update Docker Desktop / docker-ce — the old standalone `docker-compose` "
            "binary isn't sufficient; Odysseus's compose file needs the v2 plugin."
        )


def ensure_env_file(repo_root: str) -> None:
    env_path = os.path.join(repo_root, ".env")
    example_path = os.path.join(repo_root, ".env.example")
    if os.path.exists(env_path):
        step(".env already exists — leaving it untouched.")
        return
    step("No .env found — creating one from .env.example.")
    shutil.copyfile(example_path, env_path)
    print(f"    Created {env_path}")
    print("    Edit it to set OLLAMA_BASE_URL / OPENAI_API_KEY / ODYSSEUS_ADMIN_PASSWORD "
          "if you want to pre-seed them; otherwise Odysseus will prompt on first run.")


def docker_compose_up(repo_root: str) -> None:
    step("Building and starting Odysseus containers (odysseus, chromadb, searxng, ntfy)...")
    print("    This can take several minutes on first run (image build + model downloads).")
    result = subprocess.run(
        ["docker", "compose", "up", "-d", "--build"],
        cwd=repo_root,
    )
    if result.returncode != 0:
        fail("`docker compose up -d --build` failed — see the output above for the real error.")


def wait_for_health(timeout_s: int = 240) -> None:
    step(f"Waiting for Odysseus to become healthy at {HEALTH_URL} ...")
    deadline = time.time() + timeout_s
    last_err = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=3) as resp:
                if resp.status == 200:
                    print(f"\n    Odysseus is up: {APP_URL}")
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            last_err = e
        time.sleep(3)
        print(".", end="", flush=True)
    print()
    fail(
        f"Odysseus didn't report healthy within {timeout_s}s (last error: {last_err}).\n"
        "  Check logs with: docker compose logs -f odysseus"
    )


def main() -> None:
    print(f"Odysseus Docker auto-setup — platform: {platform.system()}")
    repo_root = find_repo_root()
    check_docker_installed()
    check_docker_daemon_running()
    check_compose_v2()
    ensure_env_file(repo_root)
    docker_compose_up(repo_root)
    wait_for_health()
    print("\nDone. Admin password (first run only) is in: docker compose logs odysseus")


if __name__ == "__main__":
    main()

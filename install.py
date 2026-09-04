"""
Vaultex — Interactive Installer

One command that walks through everything docs/installation.md's manual setup
otherwise has you do by hand: pick/create a vault, choose Path A (this
machine only) or Path B (Docker + Tailscale, reachable remotely), install
dependencies, set up the folder taxonomy, build the semantic-search index,
and (Path A) start the server.

Deliberately stdlib-only up until it hands off to a subprocess — this has
to run with the bare system interpreter before `pip install` has happened,
so no `dotenv`/`core.*` imports at module level. Works the same way on
Windows, macOS, and Linux: Path B runs everything inside Linux containers
regardless of host OS, and Path A goes through venv_python() below instead
of ever hardcoding a POSIX `bin/...` path.

Run:
    python3 install.py    # macOS/Linux
    python install.py     # Windows
"""

import getpass
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
VENV_DIR = BASE_DIR / ".venv"

REFERENCE_LAYOUT = [
    "00-Inbox",
    "01-Professional/Solution-Architecture/Projects",
    "01-Professional/Solution-Architecture/Analysis",
    "01-Professional/Solution-Architecture/Architecture",
    "01-Professional/Solution-Architecture/Decisions",
    "02-Builder/Ideas",
    "02-Builder/Projects",
    "03-Knowledge",
    "04-Writing",
]

DEFAULT_ROLE_MAP = {
    "builder_ideas": "02-Builder/Ideas",
    "builder_projects": "02-Builder/Projects",
    "professional_decisions": "01-Professional/Solution-Architecture/Decisions",
    "professional_tech_analysis": "01-Professional/Solution-Architecture/Analysis",
    "professional_architecture": "01-Professional/Solution-Architecture/Architecture",
    "professional_projects": "01-Professional/Solution-Architecture/Projects",
    "inbox": "00-Inbox",
}


# --- .env helpers (stdlib only — mirrors what core/config.py reads, for writing instead) ---

def _set_env(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pattern = re.compile(rf"^{re.escape(key)}=")
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _get_env(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1]
    return None


def venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python3")


# --- small prompt helpers ---

def ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = " [Y/n] " if default else " [y/N] "
    raw = input(prompt + suffix).strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def ask_choice(prompt: str, options: list[str], default: int = 1) -> int:
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}")
    raw = input(f"Choice [{default}]: ").strip()
    if not raw:
        return default
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return int(raw)
    print("Not a valid choice, using the default.")
    return default


def run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    """Streamed (inherits stdout/stderr), raises on failure — matches how
    long-running installs (pip, docker build) should surface progress.
    Every call site below passes a fixed, list-form command (sys.executable,
    "docker", venv paths) — never attacker-controlled/shell-interpreted
    input, so bandit's generic "check subprocess input" warning doesn't
    apply here."""
    print(f"\n$ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kwargs)  # noqa: S603


# --- Step 2: vault path ---

def step_vault_path() -> Path:
    if ask_yes_no("Do you have an Obsidian vault already?"):
        while True:
            raw = input("Path to your vault folder: ").strip()
            path = Path(raw).expanduser().resolve()
            if path.exists():
                return path
            if ask_yes_no(f"{path} doesn't exist. Create it?", default=False):
                path.mkdir(parents=True)
                return path
            print("Let's try again.")
    else:
        raw = input("Where should I create your new vault? [~/vaultex]: ").strip()
        path = Path(raw or "~/vaultex").expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        print(f"Created {path}")
        return path


# --- Step 5: install ---

def install_path_a() -> None:
    print("\n--- Installing (Path A: this machine only) ---")
    if not VENV_DIR.exists():
        run([sys.executable, "-m", "venv", str(VENV_DIR)])
    run([str(venv_python(VENV_DIR)), "-m", "pip", "install", "-r", str(BASE_DIR / "requirements.txt")])


def _docker_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        # Fixed command, no shell, no attacker-controlled input.
        subprocess.run(["docker", "info"], check=True, capture_output=True)  # noqa: S603, S607
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def install_path_b() -> None:
    print("\n--- Path B needs ---")
    print("  [ ] Docker Desktop installed and running")
    print("  [ ] A free Tailscale account (https://tailscale.com)")

    if not _docker_ready():
        print(
            "\nDocker isn't installed or isn't running. Install Docker Desktop "
            "(https://www.docker.com/products/docker-desktop/), start it, then re-run this installer."
        )
        raise SystemExit(1)

    if not ask_yes_no("Ready to continue?"):
        raise SystemExit(0)

    print(
        "\nGenerate a Tailscale auth key at "
        "https://login.tailscale.com/admin/settings/keys (reusable is fine — "
        "the sidecar only uses it once, to log in)."
    )
    ts_authkey = getpass.getpass("Paste your Tailscale auth key: ").strip()
    if not ts_authkey:
        raise SystemExit("No auth key entered — can't continue Path B setup.")
    _set_env(ENV_PATH, "TS_AUTHKEY", ts_authkey)

    print("\n--- Bringing the stack up (bearer-token-only mode for now) ---")
    run(["docker", "compose", "up", "-d", "--build"], cwd=BASE_DIR)

    print("\nChecking the Tailscale sidecar logged in...")
    # Fixed command, no shell, no attacker-controlled input.
    status = subprocess.run(
        ["docker", "compose", "exec", "tailscale", "tailscale", "status"],  # noqa: S603, S607
        cwd=BASE_DIR, capture_output=True, text=True,
    )
    if "logged out" in status.stdout.lower() or "invalid key" in (status.stdout + status.stderr).lower():
        raise SystemExit(
            "Tailscale couldn't log in with that auth key (it may be expired or already used). "
            "Generate a fresh key from the admin console and re-run this installer."
        )

    print("Enabling Funnel (public HTTPS) on port 8000...")
    funnel = run(
        ["docker", "compose", "exec", "tailscale", "tailscale", "funnel", "--bg", "8000"],
        cwd=BASE_DIR, capture_output=True, text=True,
    )
    match = re.search(r"https://[^\s]+\.ts\.net", funnel.stdout)
    if not match:
        raise SystemExit(f"Couldn't parse the Funnel URL from:\n{funnel.stdout}")
    issuer_url = match.group(0)
    print(f"Funnel URL: {issuer_url}")

    print(
        "\nChoose a password for the /login consent screen — you'll type this "
        "once each time a new client (e.g. Claude.ai) is authorized."
    )
    while True:
        pw1 = getpass.getpass("Authorize password: ")
        pw2 = getpass.getpass("Confirm: ")
        if pw1 and pw1 == pw2:
            break
        print("Didn't match (or was empty) — try again.")

    _set_env(ENV_PATH, "OAUTH_ISSUER_URL", issuer_url)
    _set_env(ENV_PATH, "AUTHORIZE_PASSWORD", pw1)

    print("\n--- Restarting to pick up OAuth settings ---")
    run(["docker", "compose", "up", "-d", "--build"], cwd=BASE_DIR)


# --- Step 6: folder structure ---

def step_taxonomy(vault: Path, path_choice: int) -> bool:
    """Returns True if taxonomy ended up configured (roles present)."""
    choice = ask_choice(
        "Is your vault already organized into folders (ideas, projects, decisions, etc.)?",
        [
            "Yes — let me map my own folders now (guided, ~2 min)",
            "No / not sure — use Vaultex's default layout (recommended)",
            "Skip for now — I'll run onboard.py later",
        ],
        default=2,
    )
    if choice == 1:
        if path_choice == 1:
            run([str(venv_python(VENV_DIR)), "onboard.py"], cwd=BASE_DIR)
        else:
            run(["docker", "compose", "exec", "-it", "vaultex", "python3", "onboard.py"], cwd=BASE_DIR)
        return True
    if choice == 2:
        for rel in REFERENCE_LAYOUT:
            p = vault / rel
            if not p.exists():
                p.mkdir(parents=True)
        taxonomy_path = BASE_DIR / "taxonomy.json"
        taxonomy_path.write_text(
            json.dumps({"roles": DEFAULT_ROLE_MAP, "custom_categories": []}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Scaffolded the reference layout under {vault} and wrote {taxonomy_path}")
        return True
    print("Skipped — those 8 tools will report 'not configured' until you run `onboard.py`.")
    return False


# --- Step 7: semantic index (mandatory, automatic) ---

def step_index(vault: Path, path_choice: int) -> None:
    if not any(vault.rglob("*.md")):
        print("\nVault has no notes yet — skipping the semantic-search index for now.")
        return
    print("\n--- Building the semantic-search index (this can take a minute or two) ---")
    if path_choice == 1:
        run([str(venv_python(VENV_DIR)), "index_vault.py"], cwd=BASE_DIR)
    else:
        run(["docker", "compose", "exec", "vaultex", "python3", "index_vault.py"], cwd=BASE_DIR)


# --- Step 8: summary ---

def step_summary(path_choice: int, taxonomy_configured: bool) -> None:
    token = _get_env(ENV_PATH, "MCP_AUTH_TOKEN")
    print("\n" + "=" * 60)
    print("Setup complete.")
    print("=" * 60)
    print(f"\nYour MCP_AUTH_TOKEN (keep this private): {token}")

    if path_choice == 1:
        print("\nLocal URL: http://localhost:8000/mcp")
        print(f'Authorization header: Bearer {token}')
        if not taxonomy_configured:
            print("\n(Run `python3 onboard.py` later to map your folders.)")
        if ask_yes_no("\nStart the Vaultex server now?"):
            run([str(venv_python(VENV_DIR)), "server.py"], cwd=BASE_DIR)
        else:
            print(f"Start it later with: {venv_python(VENV_DIR)} server.py")
    else:
        issuer_url = _get_env(ENV_PATH, "OAUTH_ISSUER_URL")
        print(f"\nClaude web/mobile: add a custom connector pointing at {issuer_url}/mcp")
        print("(you'll see the password screen once per client authorization)")
        print(f"\nClaude Code / CLI tools: same URL, Authorization: Bearer {token}")
        if not taxonomy_configured:
            print("\n(Run `docker compose exec -it vaultex python3 onboard.py` later to map your folders.)")


def main() -> None:
    # Without this, our print()s can appear out of order relative to
    # subprocess output when stdout isn't a tty (piped, redirected to a
    # log file, etc.). The child process writes straight to the inherited
    # fd, while our prints sit in a block buffer until it fills.
    sys.stdout.reconfigure(line_buffering=True)

    print("Vaultex — Interactive Installer\n")

    vault = step_vault_path()

    path_choice = ask_choice(
        "How do you want to use Vaultex?",
        [
            "Path A (cross interface but only one machine) — quickest, nothing exposed to the internet",
            "Path B (cross interface and multiple device) — more setup (Docker + Tailscale)",
        ],
        default=1,
    )

    if not ENV_PATH.exists():
        shutil.copy(BASE_DIR / ".env.example", ENV_PATH)
    _set_env(ENV_PATH, "VAULTEX_PATH", str(vault))

    if not _get_env(ENV_PATH, "MCP_AUTH_TOKEN"):
        import secrets
        _set_env(ENV_PATH, "MCP_AUTH_TOKEN", secrets.token_urlsafe(32))

    if path_choice == 1:
        install_path_a()
    else:
        install_path_b()

    taxonomy_configured = step_taxonomy(vault, path_choice)
    step_index(vault, path_choice)
    step_summary(path_choice, taxonomy_configured)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("\nCancelled.") from None
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"\n{e.cmd} failed with exit code {e.returncode}") from None

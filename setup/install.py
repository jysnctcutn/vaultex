"""
Vaultex — Interactive Installer

One command that walks through everything docs/installation.md's manual setup
otherwise has you do by hand: pick/create a vault, choose Path A (this
machine only) or Path B (Docker + Tailscale, reachable remotely), install
dependencies, pick a mode and a folder layout, build the semantic-search
index, and (Path A) start the server.

Four decisions, most of them a single Enter:

    Pre-flight        advisory only, never blocks
    Step 1  Vault     create new (~/vaultex) | use existing
    Step 2  Access    this machine only | + remote access
            2.1-2.3   Docker / Tailscale / authorize password (Path B only)
    Step 3  Mode      Professional (recommended) | Basic
    Step 4  Layout    only when Professional

Third-party imports are forbidden at module level: this runs on the bare
system interpreter before `pip install` has created the venv, and on Path B
it runs on the *host*, where the deps live inside the container rather than
alongside it. `core.presets` and `install_ui` are both guaranteed
dependency-free (tests/core/test_presets.py enforces it) -- every other
`core.*` module reaches dotenv through core/config.py and must stay out.

Works the same way on Windows, macOS, and Linux: Path B runs everything
inside Linux containers regardless of host OS, and Path A goes through
venv_python() below instead of ever hardcoding a POSIX `bin/...` path.

Run:
    python3 setup/install.py    # macOS/Linux
    python setup/install.py     # Windows
"""

import sys
from pathlib import Path

# Must run before every other import. install_ui and core.presets both use
# 3.10+ syntax in annotations that are evaluated at def time, so importing
# them first turns an old interpreter into a bare TypeError pointing at a
# module the user has never heard of. This is the single check standing
# between "python3 install.py" on a stock macOS 3.9 and a useful message.
# ruff reads it as dead code because it targets 3.10+; the whole point is
# that the interpreter running the installer may not be the one we target.
if sys.version_info < (3, 10):  # noqa: UP036
    raise SystemExit(
        "Vaultex needs Python 3.10 or newer; this is "
        f"{sys.version_info.major}.{sys.version_info.minor}. "
        "Install a newer Python and re-run this installer."
    )

# This file lives in setup/, so core/ is one level up and isn't on sys.path
# when the script is run directly (`python3 setup/install.py`). Must precede
# the core.presets import below.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import getpass  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import secrets  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402

import install_ui as ui  # noqa: E402
from core.presets import (  # noqa: E402
    AUTHOR_TAXONOMY,
    AUTHOR_WORKSPACES,
    DEFAULT_WORKSPACES,
    PARA_FOLDERS,
    PARA_TAXONOMY,
    POLICY_TEMPLATE_NAME,
    PRESET_AUTHOR,
    PRESET_MAPPED,
    PRESET_SIMPLE,
    SIMPLE_LABEL,
    check_name_allowed,
    mkdirs,
    seed_write_policy,
)
from install_ui import BACK, Option  # noqa: E402

# The repo root, not setup/ -- .env, .venv, taxonomy.json and the
# docker compose context all live there.
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
VENV_DIR = BASE_DIR / ".venv"
TAXONOMY_PATH = BASE_DIR / "taxonomy.json"
POLICY_TEMPLATE = BASE_DIR / POLICY_TEMPLATE_NAME

LOCAL, REMOTE = "local", "remote"
BASIC, PROFESSIONAL = "basic", "professional"


# --- .env helpers (stdlib only — mirrors what core/config.py reads, for writing instead) ---

def _upsert_env(path: Path, key: str, value: str) -> None:
    """Replace-or-append one key in .env, preserving every other line.

    This rewrites a file holding MCP_AUTH_TOKEN, TS_AUTHKEY and
    AUTHORIZE_PASSWORD, so it must never print, log, or diff what it reads --
    only the one line it owns. A Path B run calls this three times in
    sequence, so the guarantee has to hold across the whole run, not just per
    call.

    newline="" on both ends is load-bearing, not tidiness: install.py
    supports Windows, and the default universal-newline translation silently
    rewrites every CRLF in the file to LF on read. Splitting with keepends
    then preserves whatever survived that, which is the wrong thing. Reading
    untranslated and matching the file's own ending leaves untouched lines
    byte-for-byte identical.
    """
    if not path.exists():
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(f"{key}={value}\n")
        return

    with open(path, encoding="utf-8", newline="") as f:
        lines = f.read().splitlines(keepends=True)

    eol = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"
    new_line = f"{key}={value}{eol}"
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key:
            lines[i] = new_line
            break
    else:
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += eol
        lines.append(new_line)

    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("".join(lines))


def _get_env(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.split("=", 1)[0].strip() == key:
            return line.split("=", 1)[1] if "=" in line else None
    return None


def venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python3")


def run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    """Streamed (inherits stdout/stderr), raises on failure — matches how
    long-running installs (pip, docker build) should surface progress.
    Every call site below passes a fixed, list-form command (sys.executable,
    "docker", venv paths) — never attacker-controlled/shell-interpreted
    input, so bandit's generic "check subprocess input" warning doesn't
    apply here."""
    print(f"\n$ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kwargs)  # noqa: S603


def _docker_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        # Fixed command, no shell, no attacker-controlled input.
        subprocess.run(["docker", "info"], check=True, capture_output=True)  # noqa: S603, S607
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def _in_vault(vault: Path, command: str, access: str) -> str:
    """The command a user types later, spelled for the path they installed."""
    if access == REMOTE:
        return f"docker compose exec -it vaultex python3 {command}"
    return f"{venv_python(VENV_DIR)} {command}"


# --- Pre-flight: advisory only, never blocks ---

def preflight() -> None:
    findings = []
    if not (BASE_DIR / ".env.example").exists():
        findings.append("No .env.example found — is this a complete checkout?")
    if _get_env(ENV_PATH, "VAULTEX_PATH"):
        findings.append("An existing .env was found; this run updates it in place.")
    if not findings:
        return
    print()
    for line in findings:
        print(f"  note: {line}")


# --- Step 1: vault ---

def step_vault() -> Path:
    have = ui.select(
        "Vault",
        "Step 1 of 4",
        [
            Option("new", "Create a new vault", [
                "A fresh folder Vaultex sets up for you.",
            ], recommended=True),
            Option("existing", "Use an Obsidian vault I already have", [
                "Point Vaultex at it; nothing in it is moved or renamed.",
            ]),
        ],
    )

    if have == "new":
        raw = ui.ask_text("Where should I create it?", "~/vaultex")
        path = Path(raw).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    while True:
        raw = ui.ask_text("Path to your vault folder")
        path = Path(raw).expanduser().resolve()
        if path.exists():
            return path
        if ui.ask_yes_no(f"{path} doesn't exist. Create it?", default=False):
            path.mkdir(parents=True)
            return path
        print("Let's try again.")


# --- Step 2: access ---

def step_access() -> str:
    return ui.select(
        "Access",
        "Step 2 of 4",
        [
            Option(LOCAL, "This machine only", [
                "Everything runs in a local venv. Nothing is exposed to the internet.",
                "Works with Claude Code and any local MCP client.",
            ], recommended=True),
            Option(REMOTE, "This machine + remote access", [
                "Docker plus Tailscale, so Claude.ai and your other devices can reach "
                "the same vault.",
                "More setup: three extra questions.",
            ]),
        ],
        allow_back=True,
    )


def install_path_a() -> None:
    print("\n--- Installing (this machine only) ---")
    if not VENV_DIR.exists():
        run([sys.executable, "-m", "venv", str(VENV_DIR)])
    run([str(venv_python(VENV_DIR)), "-m", "pip", "install", "-r", str(BASE_DIR / "requirements.txt")])


def install_path_b() -> str:
    """Returns the access mode actually installed — a missing Docker downgrades
    to a local install rather than dead-ending, so every path through this
    wizard still finishes with a working Vaultex."""
    if not _docker_ready():
        choice = ui.select(
            "Docker not available",
            "Step 2.1 of 4",
            [
                Option(LOCAL, "Continue as a local install", [
                    "Sets Vaultex up for this machine only. You can re-run this "
                    "installer and choose remote access once Docker is running — "
                    "nothing here has to be undone.",
                ], recommended=True),
                Option("stop", "Stop so I can install Docker first", [
                    "Get Docker Desktop from docker.com, start it, then re-run this "
                    "installer.",
                ]),
            ],
        )
        if choice == LOCAL:
            ui.step_done("Access", "this machine only (Docker unavailable)")
            install_path_a()
            return LOCAL
        raise SystemExit(
            "\nInstall Docker Desktop (https://www.docker.com/products/docker-desktop/), "
            "start it, then re-run this installer."
        )

    print("\n--- Step 2.2 of 4: Tailscale ---")
    ui.note(
        "Tailscale puts this machine on a private network only your own "
        "devices can reach. Nothing is published to the open internet."
    )
    print(
        "\nGenerate an auth key at "
        "https://login.tailscale.com/admin/settings/keys (reusable is fine — "
        "the sidecar only uses it once, to log in)."
    )
    ts_authkey = getpass.getpass("Paste your Tailscale auth key: ").strip()
    if not ts_authkey:
        raise SystemExit("No auth key entered — can't continue remote setup.")
    _upsert_env(ENV_PATH, "TS_AUTHKEY", ts_authkey)

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

    print("\n--- Step 2.3 of 4: authorize password ---")
    print("Two questions left.")
    ui.note(
        "Choose a password for the /login consent screen — you'll type this "
        "once each time a new client (e.g. Claude.ai) is authorized."
    )
    while True:
        pw1 = getpass.getpass("Authorize password: ")
        pw2 = getpass.getpass("Confirm: ")
        if pw1 and pw1 == pw2:
            break
        print("Didn't match (or was empty) — try again.")

    _upsert_env(ENV_PATH, "OAUTH_ISSUER_URL", issuer_url)
    _upsert_env(ENV_PATH, "AUTHORIZE_PASSWORD", pw1)

    print("\n--- Restarting to pick up OAuth settings ---")
    run(["docker", "compose", "up", "-d", "--build"], cwd=BASE_DIR)
    return REMOTE


# --- Step 3: mode ---

def step_mode() -> str:
    """Mode is chosen here, not in onboard.py: it changes the registered
    toolset (31 vs 4), so someone who picks Basic and later wonders where
    save_decision went needs to remember making the choice. onboard.py is the
    taxonomy specialist; owning the top-level product concept there too was
    the split-brain this flow exists to fix."""
    return ui.select(
        "Mode",
        "Step 3 of 4",
        [
            Option(PROFESSIONAL, "Professional", [
                "31 tools: save_decision, save_brainstorm, the episodic session log, "
                "distillation, per-category get/create, and multi-agent coordination.",
                "Notes are routed, named, section-checked and cross-linked for you.",
                "VAULTEX_MODE=professional",
            ], recommended=True),
            Option(BASIC, "Basic", [
                "4 tools: search, grep, read_note, write_note. No taxonomy, no folder "
                "roles, no imposed structure — write_note takes an explicit path and "
                "does nothing clever with it.",
                "Best if you already have your own folder conventions.",
                "VAULTEX_MODE=basic",
            ]),
        ],
        allow_back=False,  # dependencies are already installed by this point
        footer="Switchable later by editing VAULTEX_MODE in .env. Either way, "
               "taxonomy.json is never modified by this choice.",
    )


# --- Step 4: layout (Professional only) ---

def _vault_is_populated(vault: Path) -> bool:
    """Someone with folders and notes already needs a different default from
    someone starting empty — pre-selecting a scaffold that creates four new
    top-level folders is wrong for a vault with 400 notes in it."""
    if any(vault.rglob("*.md")):
        return True
    return any(p.is_dir() and not p.name.startswith(".") for p in vault.iterdir())


def _write_taxonomy(roles: dict, workspaces: dict, preset: str) -> None:
    """Merges into an existing taxonomy.json rather than replacing it, so
    re-running the installer can't drop custom categories or project
    subfolders someone configured through onboard.py."""
    existing = {}
    if TAXONOMY_PATH.exists():
        try:
            existing = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
        except ValueError:
            existing = {}

    for name in workspaces["entries"]:
        check_name_allowed(name)

    data = {
        **existing,
        "preset": preset,
        "roles": {**existing.get("roles", {}), **roles},
        "custom_categories": existing.get("custom_categories", []),
        "workspaces": workspaces,
    }
    TAXONOMY_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _apply_simple(vault: Path) -> None:
    mkdirs(vault, PARA_FOLDERS)
    mkdirs(vault, PARA_TAXONOMY.values())
    mkdirs(vault, DEFAULT_WORKSPACES["entries"].values())
    _write_taxonomy(PARA_TAXONOMY, DEFAULT_WORKSPACES, PRESET_SIMPLE)
    seed_write_policy(vault, POLICY_TEMPLATE)


def _apply_author(vault: Path) -> None:
    mkdirs(vault, AUTHOR_TAXONOMY.values())
    mkdirs(vault, AUTHOR_WORKSPACES["entries"].values())
    _write_taxonomy(AUTHOR_TAXONOMY, AUTHOR_WORKSPACES, PRESET_AUTHOR)
    seed_write_policy(vault, POLICY_TEMPLATE)


def _run_onboard(access: str) -> None:
    if access == REMOTE:
        run(["docker", "compose", "exec", "-it", "vaultex", "python3", "setup/onboard.py"], cwd=BASE_DIR)
    else:
        run([str(venv_python(VENV_DIR)), "setup/onboard.py"], cwd=BASE_DIR)


def step_layout(vault: Path, access: str) -> str:
    """Returns the preset applied, for the collapsed summary line."""
    simple = Option(PRESET_SIMPLE, SIMPLE_LABEL, [
        "Inbox for anything unsorted, Projects for active work, Areas for ongoing "
        "topics, Resources for reference.",
        "(a PARA-style layout)",
    ])
    mapped = Option(PRESET_MAPPED, "Map my existing folders", [
        "Guided, about 2 minutes. Points each role at folders you already have, so "
        "nothing is moved or renamed.",
    ])

    if _vault_is_populated(vault):
        # Author's layout is hidden here on purpose: it scaffolds a specific
        # 01-Professional/02-Builder tree, which is the wrong offer for a
        # vault that already has its own.
        mapped.recommended = True
        alongside = Option(PRESET_SIMPLE, f"Add the {SIMPLE_LABEL.lower()} alongside", [
            "Creates the four folders next to what you already have and maps the "
            "roles onto them. Existing folders are left alone.",
        ])
        choice = ui.select(
            "Layout", "Step 4 of 4", [mapped, alongside], allow_back=True,
            footer="Your vault already has folders, so the author's layout isn't offered "
                   "here — run `setup/onboard.py --advanced` if you want it.",
        )
    else:
        simple.recommended = True
        author = Option(PRESET_AUTHOR, "Use the author's layout", [
            "JC's own structure: 00-Inbox, 01-Professional/..., 02-Builder/...",
            "A starting point if it happens to match how you think.",
        ])
        choice = ui.select("Layout", "Step 4 of 4", [simple, mapped, author], allow_back=True)

    if choice == BACK:
        return BACK
    if choice == PRESET_SIMPLE:
        _apply_simple(vault)
    elif choice == PRESET_AUTHOR:
        _apply_author(vault)
    else:
        _run_onboard(access)
    return choice


# --- Semantic index ---

def step_index(vault: Path, access: str) -> None:
    if not any(vault.rglob("*.md")):
        print("\nVault has no notes yet — skipping the semantic-search index for now.")
        return
    print("\n--- Building the semantic-search index (this can take a minute or two) ---")
    if access == REMOTE:
        run(["docker", "compose", "exec", "vaultex", "python3", "index_vault.py"], cwd=BASE_DIR)
    else:
        run([str(venv_python(VENV_DIR)), "index_vault.py"], cwd=BASE_DIR)


# --- Summary ---

def _later_block(vault: Path, access: str, mode: str) -> None:
    """Required after every successful run (decision §3): the one place a
    user learns that the choices this wizard made for them are reversible."""
    print("\nLater, when you want more control:")
    if mode == PROFESSIONAL:
        print(f"  - Add a workspace          {_in_vault(vault, 'setup/onboard.py --add-workspace', access)}")
        print(f"  - Map roles precisely      {_in_vault(vault, 'setup/onboard.py', access)}")
        print(f"  - Tune write behaviour     edit {vault / 'write_policy.md'}")
    else:
        print("  - Switch to Professional   set VAULTEX_MODE=professional in .env, then run")
        print(f"                             {_in_vault(vault, 'setup/onboard.py', access)}")
    if access == LOCAL:
        print("  - Switch to remote access  re-run setup/install.py and choose remote access")


def step_summary(vault: Path, access: str, mode: str) -> None:
    token = _get_env(ENV_PATH, "MCP_AUTH_TOKEN")
    print("\n" + "=" * 60)
    print("Setup complete.")
    print("=" * 60)
    print(f"\nYour MCP_AUTH_TOKEN (keep this private): {token}")

    if access == LOCAL:
        print("\nLocal URL: http://localhost:8000/mcp")
        print(f"Authorization header: Bearer {token}")
        _later_block(vault, access, mode)
        if ui.ask_yes_no("\nStart the Vaultex server now?"):
            run([str(venv_python(VENV_DIR)), "server.py"], cwd=BASE_DIR)
        else:
            print(f"Start it later with: {venv_python(VENV_DIR)} server.py")
    else:
        issuer_url = _get_env(ENV_PATH, "OAUTH_ISSUER_URL")
        print(f"\nClaude web/mobile: add a custom connector pointing at {issuer_url}/mcp")
        print("(you'll see the password screen once per client authorization)")
        print(f"\nClaude Code / CLI tools: same URL, Authorization: Bearer {token}")
        _later_block(vault, access, mode)


def main() -> None:
    # Without this, our print()s can appear out of order relative to
    # subprocess output when stdout isn't a tty (piped, redirected to a
    # log file, etc.). The child process writes straight to the inherited
    # fd, while our prints sit in a block buffer until it fills.
    sys.stdout.reconfigure(line_buffering=True)

    print("Vaultex — Interactive Installer")
    preflight()

    # `b` reaches only the immediately previous step, which is all the locked
    # flow needs — and all a hand-rolled selector can redraw reliably.
    while True:
        vault = step_vault()
        ui.step_done("Vault", str(vault))
        access = step_access()
        if access != BACK:
            break

    if not ENV_PATH.exists():
        shutil.copy(BASE_DIR / ".env.example", ENV_PATH)
    _upsert_env(ENV_PATH, "VAULTEX_PATH", str(vault))
    if not _get_env(ENV_PATH, "MCP_AUTH_TOKEN"):
        _upsert_env(ENV_PATH, "MCP_AUTH_TOKEN", secrets.token_urlsafe(32))

    if access == LOCAL:
        ui.step_done("Access", "this machine only")
        install_path_a()
    else:
        access = install_path_b()
        if access == REMOTE:
            ui.step_done("Access", "this machine + remote")

    mode = step_mode()
    _upsert_env(ENV_PATH, "VAULTEX_MODE", mode)
    ui.step_done("Mode", mode)

    if mode == BASIC:
        # Terminates here by design: Basic has no taxonomy, so there is no
        # layout to choose. Saying so beats a fourth screen that does nothing.
        print("\nBasic mode is ready — search, grep, read_note, write_note.")
        print("Step 4 (layout) doesn't apply: Basic imposes no folder structure.")
        step_index(vault, access)
        step_summary(vault, access, mode)
        return

    while True:
        preset = step_layout(vault, access)
        if preset != BACK:
            break
        mode = step_mode()
        _upsert_env(ENV_PATH, "VAULTEX_MODE", mode)
        ui.step_done("Mode", mode)
        if mode == BASIC:
            step_index(vault, access)
            step_summary(vault, access, mode)
            return
    ui.step_done("Layout", preset)

    step_index(vault, access)
    step_summary(vault, access, mode)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("\nCancelled.") from None
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"\n{e.cmd} failed with exit code {e.returncode}") from None

"""
Vaultex — installer wizard UI (stdlib only)

`install.py` runs on the bare system interpreter *before* `pip install` has
happened, so this module may not import rich, questionary, readchar, or
anything else off PyPI. Everything below is termios/msvcrt plus ANSI escapes.

Constraints come from the Easy Install & Onboarding UX decision §9.5:

  - Framed step panels with a step indicator; arrow keys move, Enter
    confirms, `b` goes back one step.
  - Output must survive in scrollback, so no alternate screen buffer. A
    full-screen TUI clears on exit and takes the summary and the "Later"
    command block with it -- exactly what a Path B user scrolling back
    through `docker compose exec` output needs to still be there.
  - An answered step collapses to one line (`  ok  Mode  professional`) as
    the wizard advances, so the terminal accumulates a short history rather
    than eight stacked panels. That accumulated history *is* the summary.
  - Numbered-prompt fallback whenever stdin or stdout isn't a TTY.
"""

import os
import sys
import textwrap
from dataclasses import dataclass, field

WIDTH = 68
BACK = "\x00vaultex-back"

_ESC = "\x1b["
_DIM = f"{_ESC}2m"
_BOLD = f"{_ESC}1m"
_RESET = f"{_ESC}0m"


@dataclass
class Option:
    """One choice on a step panel. `lines` carries the 3-5 line explainer the
    locked screens call for -- the reason a hand-rolled selector beat every
    library surveyed, all of which want a single string per choice."""

    value: str
    label: str
    lines: list[str] = field(default_factory=list)
    recommended: bool = False


def _interactive() -> bool:
    if os.environ.get("VAULTEX_INSTALL_PLAIN"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def _enable_windows_vt() -> None:
    """Win10+ consoles understand ANSI, but only after the mode bit is set."""
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:  # noqa: BLE001, S110 - cosmetic only; plain output still works
        pass


# --- panel rendering ---------------------------------------------------------

def _wrap(text: str, indent: int) -> list[str]:
    room = WIDTH - 4 - indent
    return textwrap.wrap(text, width=room) or [""]


def _row(content: str = "", visible_len: int | None = None) -> str:
    """One framed line. `visible_len` is the printable width when `content`
    carries ANSI codes, which don't occupy columns."""
    length = len(content) if visible_len is None else visible_len
    return f"| {content}{' ' * max(0, WIDTH - 4 - length)} |"


def _panel(title: str, step: str, options: list[Option], cursor: int, footer: str) -> list[str]:
    # A title longer than the frame used to clamp the padding to zero and push
    # the corner off the end, breaking the box. Truncate the title instead --
    # the step indicator is the part that has to stay readable.
    prefix = f"-- {step} -- "
    room = WIDTH - 2 - len(prefix) - 1
    if room < 1:
        prefix, room = "", WIDTH - 3
    shown = title if len(title) <= room else title[: max(0, room - 1)] + "~"
    head = f"{prefix}{shown} "
    lines = [f"+{head}{'-' * (WIDTH - 2 - len(head))}+", _row()]

    for i, opt in enumerate(options):
        selected = i == cursor
        marker = "(*)" if selected else "( )"
        label = opt.label + ("  (recommended)" if opt.recommended else "")
        plain = f" {marker} {label}"
        styled = f" {marker} {_BOLD}{label}{_RESET}" if selected else f"{_DIM} {marker} {label}{_RESET}"
        lines.append(_row(styled, visible_len=len(plain)))
        for raw in opt.lines:
            for wrapped in _wrap(raw, indent=6):
                lines.append(_row(f"{_DIM}      {wrapped}{_RESET}", visible_len=6 + len(wrapped)))
        lines.append(_row())

    if footer:
        for wrapped in _wrap(footer, indent=1):
            lines.append(_row(f"{_DIM} {wrapped}{_RESET}", visible_len=1 + len(wrapped)))
        lines.append(_row())

    lines.append(f"+{'-' * (WIDTH - 2)}+")
    return lines


# --- key reading -------------------------------------------------------------

# Escape sequence tails, once the leading ESC has been consumed.
_ARROWS = {"[A": "up", "[B": "down"}


def _decode(ch: str, tail: str = "") -> str:
    """One keypress -> a name. Pure, so the mapping is testable without a tty;
    `tail` is the two characters following an ESC, empty for a bare Escape.

    Raw mode turns off ISIG, so the SIGINT a user expects from Ctrl-C never
    fires -- raising it here is what keeps Ctrl-C working at all.
    """
    if ch == "\x03":
        raise KeyboardInterrupt
    if ch == "\x1b":
        return _ARROWS.get(tail, "escape" if not tail else "")
    return {"\r": "enter", "\n": "enter"}.get(ch, ch.lower())


def _read_key() -> str:
    if os.name == "nt":
        import msvcrt

        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            return {"H": "up", "P": "down"}.get(msvcrt.getwch(), "")
        return _decode(ch)

    import termios
    import tty

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        tail = ""
        if ch == "\x1b":
            # Tell an arrow sequence from a bare Escape without blocking on
            # the latter, which sends nothing more.
            import select as _select

            if _select.select([sys.stdin], [], [], 0.05)[0]:
                tail = sys.stdin.read(2)
    finally:
        # Before anything can raise: a wizard that exits with ICANON and ECHO
        # still off leaves the user's shell unusable.
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)

    return _decode(ch, tail)


# --- public surface ----------------------------------------------------------

def rule(text: str = "") -> None:
    print(f"\n{text}" if text else "")


def step_done(label: str, value: str) -> None:
    """The collapsed one-line record an answered step leaves behind."""
    print(f"  ok  {label:<10} {value}")


def note(text: str) -> None:
    for line in textwrap.wrap(text, width=WIDTH):
        print(f"      {line}")


def select(
    title: str,
    step: str,
    options: list[Option],
    default: int = 0,
    allow_back: bool = False,
    footer: str = "",
) -> str:
    """Draw one step panel and return the chosen option's value, or BACK.

    Redraws in place, then erases the panel on confirm so the caller can
    replace it with a collapsed one-liner.
    """
    if not _interactive():
        return _select_plain(title, step, options, default, allow_back, footer)

    _enable_windows_vt()
    cursor = default
    hint = "  up/down move . enter select" + (" . b back" if allow_back else "")
    drawn = 0

    while True:
        lines = _panel(title, step, options, cursor, footer) + [f"{_DIM}{hint}{_RESET}"]
        if drawn:
            sys.stdout.write(f"{_ESC}{drawn}A")
        sys.stdout.write("".join(f"{_ESC}2K{line}\n" for line in lines))
        sys.stdout.flush()
        drawn = len(lines)

        key = _read_key()
        if key == "up":
            cursor = (cursor - 1) % len(options)
        elif key == "down":
            cursor = (cursor + 1) % len(options)
        elif key == "enter":
            break
        elif key == "b" and allow_back:
            cursor = -1
            break

    # Erase the panel: the collapsed line the caller prints next takes its place.
    sys.stdout.write(f"{_ESC}{drawn}A{_ESC}0J")
    sys.stdout.flush()
    return BACK if cursor == -1 else options[cursor].value


def _select_plain(
    title: str,
    step: str,
    options: list[Option],
    default: int,
    allow_back: bool,
    footer: str,
) -> str:
    """Numbered fallback for a pipe, a log file, or a terminal that can't do
    raw mode. Same information, no redrawing."""
    print(f"\n-- {step} -- {title}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt.label}{'  (recommended)' if opt.recommended else ''}")
        for raw in opt.lines:
            note(raw)
    if footer:
        print()
        note(footer)

    suffix = " (or 'b' to go back)" if allow_back else ""
    while True:
        raw = input(f"Choice [{default + 1}]{suffix}: ").strip().lower()
        if not raw:
            return options[default].value
        if allow_back and raw == "b":
            return BACK
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1].value
        print("Not a valid choice — try again.")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    raw = input(f"{prompt}{' [Y/n] ' if default else ' [y/N] '}").strip().lower()
    return default if not raw else raw in ("y", "yes")


def ask_text(prompt: str, default: str = "") -> str:
    shown = f"{prompt} [{default}]: " if default else f"{prompt}: "
    return input(shown).strip() or default

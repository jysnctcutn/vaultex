"""The installer's hand-rolled selector.

Decision §9.5 ruled out every off-the-shelf option: install.py runs on the
bare system interpreter before pip has run, and on Path B it runs on the
host where the deps live in the container. So this is termios + ANSI, and
the parts worth testing are the ones a library would otherwise guarantee --
that the frame lines up, that a pipe still gets a usable prompt, and that
`b` reaches the previous step.
"""

import re

import pytest

import install_ui
from install_ui import BACK, Option

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

OPTIONS = [
    Option("professional", "Professional", ["30 tools.", "VAULTEX_MODE=professional"], recommended=True),
    Option("basic", "Basic", ["4 tools."]),
]


@pytest.fixture
def plain(monkeypatch):
    """Force the numbered fallback — the path a pipe, a log file, or a
    terminal that can't do raw mode takes."""
    monkeypatch.setattr(install_ui, "_interactive", lambda: False)


def _answers(monkeypatch, *values):
    it = iter(values)
    monkeypatch.setattr("builtins.input", lambda *_: next(it))


# --- framing -----------------------------------------------------------------

def test_every_panel_line_is_the_same_visible_width():
    """ANSI codes occupy no columns, so the frame only lines up if the
    renderer measures printable length rather than len(str)."""
    lines = install_ui._panel("Mode", "Step 3 of 4", OPTIONS, 0, "Switchable later.")
    widths = {len(_ANSI.sub("", line)) for line in lines}
    assert widths == {install_ui.WIDTH}


def test_the_selected_option_is_the_marked_one():
    first = _ANSI.sub("", "\n".join(install_ui._panel("Mode", "Step 3 of 4", OPTIONS, 0, "")))
    second = _ANSI.sub("", "\n".join(install_ui._panel("Mode", "Step 3 of 4", OPTIONS, 1, "")))
    assert "(*) Professional" in first and "( ) Basic" in first
    assert "( ) Professional" in second and "(*) Basic" in second


def test_explainer_lines_reach_the_panel():
    """The reason a custom selector beat every library surveyed: each option
    carries 3-5 lines, not one string."""
    body = _ANSI.sub("", "\n".join(install_ui._panel("Mode", "Step 3 of 4", OPTIONS, 0, "")))
    assert "VAULTEX_MODE=professional" in body
    assert "30 tools." in body


@pytest.mark.parametrize("title", [
    "Mode",
    "Default folder for captured brainstorms/conversation conclusions",
    "Append-only agent session/event log (log_event, start_session, close_session)",
    "x" * 200,
])
def test_a_long_title_cannot_break_the_frame(title):
    """The title bar is the one place text can't wrap. Padding used to clamp
    to zero and push the corner past the edge, so onboard's longer role
    descriptions split the box open."""
    lines = install_ui._panel(title, "Role 6 of 7", OPTIONS, 0, "")
    assert {len(_ANSI.sub("", line)) for line in lines} == {install_ui.WIDTH}


def test_a_long_step_indicator_cannot_break_the_frame():
    lines = install_ui._panel("Mode", "Step " + "9" * 120, OPTIONS, 0, "")
    assert {len(_ANSI.sub("", line)) for line in lines} == {install_ui.WIDTH}


def test_a_long_explainer_wraps_instead_of_breaking_the_frame():
    long_option = [Option("x", "X", ["word " * 60])]
    lines = install_ui._panel("T", "Step 1 of 4", long_option, 0, "")
    assert {len(_ANSI.sub("", line)) for line in lines} == {install_ui.WIDTH}


def test_the_recommended_marker_is_shown():
    body = _ANSI.sub("", "\n".join(install_ui._panel("Mode", "Step 3 of 4", OPTIONS, 0, "")))
    assert "Professional  (recommended)" in body


# --- the non-TTY fallback ----------------------------------------------------

def test_enter_takes_the_default(plain, monkeypatch):
    _answers(monkeypatch, "")
    assert install_ui.select("Mode", "Step 3 of 4", OPTIONS) == "professional"


def test_the_default_is_configurable(plain, monkeypatch):
    _answers(monkeypatch, "")
    assert install_ui.select("Mode", "Step 3 of 4", OPTIONS, default=1) == "basic"


def test_a_number_picks_that_option(plain, monkeypatch):
    _answers(monkeypatch, "2")
    assert install_ui.select("Mode", "Step 3 of 4", OPTIONS) == "basic"


def test_an_invalid_choice_reprompts_rather_than_guessing(plain, monkeypatch):
    _answers(monkeypatch, "9", "nonsense", "1")
    assert install_ui.select("Mode", "Step 3 of 4", OPTIONS) == "professional"


def test_b_goes_back_when_the_step_allows_it(plain, monkeypatch):
    _answers(monkeypatch, "b")
    assert install_ui.select("Mode", "Step 3 of 4", OPTIONS, allow_back=True) == BACK


def test_b_is_just_an_invalid_choice_when_back_is_closed(plain, monkeypatch):
    """Step 3 forbids going back: dependencies are already installed by then."""
    _answers(monkeypatch, "b", "2")
    assert install_ui.select("Mode", "Step 3 of 4", OPTIONS, allow_back=False) == "basic"


def test_the_fallback_still_prints_the_explainers(plain, monkeypatch, capsys):
    _answers(monkeypatch, "")
    install_ui.select("Mode", "Step 3 of 4", OPTIONS, footer="Switchable later.")
    out = capsys.readouterr().out
    assert "VAULTEX_MODE=professional" in out
    assert "Switchable later." in out


def test_a_piped_stdin_is_not_treated_as_interactive(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    assert install_ui._interactive() is False


def test_a_dumb_terminal_is_not_treated_as_interactive(monkeypatch):
    monkeypatch.setenv("TERM", "dumb")
    assert install_ui._interactive() is False


def test_the_collapsed_line_records_the_answer(capsys):
    install_ui.step_done("Mode", "professional")
    assert "Mode" in capsys.readouterr().out


# --- the interactive path ----------------------------------------------------
#
# Everything above exercises the numbered fallback. These cover the raw-mode
# selector a user actually meets, split in two so neither needs a live tty:
# _decode maps keypresses, and select()'s loop is driven through a scripted
# _read_key.


@pytest.mark.parametrize(("ch", "tail", "expected"), [
    ("\x1b", "[A", "up"),
    ("\x1b", "[B", "down"),
    ("\x1b", "", "escape"),        # a bare Escape sends nothing more
    ("\x1b", "[C", ""),            # left/right: ignored, not misread as a move
    ("\r", "", "enter"),
    ("\n", "", "enter"),
    ("b", "", "b"),
    ("B", "", "b"),                # shift shouldn't defeat "b goes back"
])
def test_keypresses_decode_to_the_right_action(ch, tail, expected):
    assert install_ui._decode(ch, tail) == expected


def test_ctrl_c_interrupts_even_though_raw_mode_disabled_the_signal():
    """Raw mode turns off ISIG, so the SIGINT a user expects never fires --
    without this the installer would ignore Ctrl-C entirely."""
    with pytest.raises(KeyboardInterrupt):
        install_ui._decode("\x03")


@pytest.fixture
def keys(monkeypatch):
    """Drive select()'s real interactive loop with a scripted key sequence."""
    monkeypatch.setattr(install_ui, "_interactive", lambda: True)

    def script(*presses):
        it = iter(presses)
        monkeypatch.setattr(install_ui, "_read_key", lambda: next(it))
    return script


def test_enter_confirms_the_highlighted_option(keys, capsys):
    keys("enter")
    assert install_ui.select("Mode", "Step 3 of 4", OPTIONS) == "professional"


def test_the_down_arrow_moves_the_cursor(keys):
    keys("down", "enter")
    assert install_ui.select("Mode", "Step 3 of 4", OPTIONS) == "basic"


def test_the_up_arrow_wraps_to_the_last_option(keys):
    keys("up", "enter")
    assert install_ui.select("Mode", "Step 3 of 4", OPTIONS) == "basic"


def test_down_then_up_returns_to_the_first(keys):
    keys("down", "up", "enter")
    assert install_ui.select("Mode", "Step 3 of 4", OPTIONS) == "professional"


def test_unknown_keys_are_ignored_rather_than_confirming(keys):
    keys("", "escape", "z", "enter")
    assert install_ui.select("Mode", "Step 3 of 4", OPTIONS) == "professional"


def test_b_goes_back_through_the_interactive_loop(keys):
    keys("b")
    assert install_ui.select("Mode", "Step 3 of 4", OPTIONS, allow_back=True) == BACK


def test_b_does_not_go_back_when_the_step_forbids_it(keys):
    """Step 3 forbids it: dependencies are already installed by then."""
    keys("b", "down", "enter")
    assert install_ui.select("Mode", "Step 3 of 4", OPTIONS, allow_back=False) == "basic"


def test_the_scrollback_is_not_wiped(keys, capsys):
    """No alternate screen buffer: a full-screen TUI clears on exit and takes
    the summary and the "Later" command block with it."""
    keys("enter")
    install_ui.select("Mode", "Step 3 of 4", OPTIONS)
    assert "?1049h" not in capsys.readouterr().out


def test_the_panel_rewinds_instead_of_stacking(keys, capsys):
    keys("down", "enter")
    install_ui.select("Mode", "Step 3 of 4", OPTIONS)
    assert re.search(r"\x1b\[\d+A", capsys.readouterr().out)


def test_the_panel_is_erased_so_a_collapsed_line_can_replace_it(keys, capsys):
    keys("enter")
    install_ui.select("Mode", "Step 3 of 4", OPTIONS)
    assert "\x1b[0J" in capsys.readouterr().out

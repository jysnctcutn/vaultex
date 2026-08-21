import core.mcp_app as mcp_app_mod
from core.mcp_app import move_tool, register_tool, write_tool


def _dummy():
    return "dummy"


def test_write_tool_registers_when_not_read_only(monkeypatch):
    monkeypatch.setattr(mcp_app_mod, "READ_ONLY", False)
    result = write_tool(_dummy)
    assert result is _dummy


def test_write_tool_skips_registration_when_read_only(monkeypatch):
    monkeypatch.setattr(mcp_app_mod, "READ_ONLY", True)
    result = write_tool(_dummy)
    assert result is _dummy


def test_move_tool_skips_registration_when_read_only(monkeypatch):
    monkeypatch.setattr(mcp_app_mod, "READ_ONLY", True)
    monkeypatch.setattr(mcp_app_mod, "ENABLE_NOTE_MOVE", True)
    result = move_tool(_dummy)
    assert result is _dummy


def test_move_tool_skips_registration_when_note_move_disabled(monkeypatch):
    monkeypatch.setattr(mcp_app_mod, "READ_ONLY", False)
    monkeypatch.setattr(mcp_app_mod, "ENABLE_NOTE_MOVE", False)
    result = move_tool(_dummy)
    assert result is _dummy


def test_move_tool_registers_when_enabled_and_not_read_only(monkeypatch):
    monkeypatch.setattr(mcp_app_mod, "READ_ONLY", False)
    monkeypatch.setattr(mcp_app_mod, "ENABLE_NOTE_MOVE", True)
    result = move_tool(_dummy)
    assert result is _dummy


def test_register_tool_skips_write_tool_when_read_only(monkeypatch):
    monkeypatch.setattr(mcp_app_mod, "READ_ONLY", True)
    result = register_tool(_dummy, name="dummy_tool", description="a dummy tool", write=True)
    assert result is _dummy


def test_register_tool_registers_read_tool_regardless_of_read_only(monkeypatch):
    monkeypatch.setattr(mcp_app_mod, "READ_ONLY", True)
    result = register_tool(_dummy, name="dummy_read_tool", description="a dummy read tool", write=False)
    assert result is _dummy

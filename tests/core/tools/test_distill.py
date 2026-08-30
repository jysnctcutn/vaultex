import uuid
from pathlib import Path

import pytest

import core.tools.episodic as episodic_mod
import core.tools.open_questions as oq_mod
from core.tools.distill import apply_distillation, distill_session
from core.vault import read, safe_path, write


@pytest.fixture
def memory_roots(monkeypatch):
    ep = Path(f"02-Builder/Episodic-{uuid.uuid4().hex[:8]}")
    oq = Path(f"02-Builder/OpenQuestions-{uuid.uuid4().hex[:8]}")
    monkeypatch.setattr(episodic_mod, "EPISODIC", ep)
    monkeypatch.setattr(oq_mod, "OPEN_QUESTIONS", oq)
    yield {"episodic": ep, "open_questions": oq}


def _closed_session(project="DistillProj", goal="ship the thing"):
    path = episodic_mod.start_session(project, goal, agents=["dev", "ba"])
    episodic_mod.close_session(path, "done")
    return path


# --- distill_session (read-only bundler) ---

def test_distill_session_rejects_missing_file(memory_roots):
    with pytest.raises(FileNotFoundError):
        distill_session("02-Builder/Episodic/nope.md")


def test_distill_session_rejects_non_episodic_note(memory_roots):
    write(safe_path("02-Builder/Projects/DistillProj/Notes.md"), "not episodic", overwrite=True)
    with pytest.raises(ValueError, match="not an episodic note"):
        distill_session("02-Builder/Projects/DistillProj/Notes.md")


def test_distill_session_returns_bundle_with_schema_and_context(memory_roots):
    write(safe_path("02-Builder/Projects/DistillProj/Existing.md"), "durable note", overwrite=True)
    session_path = _closed_session()

    bundle = distill_session(session_path)

    assert bundle["project"] == "DistillProj"
    assert bundle["session"]["path"] == session_path
    assert "## Outcome" in bundle["session"]["content"]
    assert bundle["already_promoted"] is False
    assert bundle["session_status"] == "closed"
    assert "new_decisions" in bundle["proposal_schema"]
    assert any("Existing.md" in n["path"] for n in bundle["project_context"])


# --- apply_distillation (gated write-back) ---

def test_apply_distillation_requires_confirm(memory_roots):
    session_path = _closed_session()
    with pytest.raises(ValueError, match="confirm=True"):
        apply_distillation(session_path, {"new_decisions": []})


def test_apply_distillation_rejects_unknown_proposal_key(memory_roots):
    session_path = _closed_session()
    with pytest.raises(ValueError, match="Unknown proposal key"):
        apply_distillation(session_path, {"bogus": []}, confirm=True)


def test_apply_distillation_rejects_decision_without_body(memory_roots):
    session_path = _closed_session()
    with pytest.raises(ValueError, match="non-empty 'title' and 'body'"):
        apply_distillation(session_path, {"new_decisions": [{"title": "x"}]}, confirm=True)


def test_apply_distillation_creates_decisions_and_questions_with_provenance(memory_roots):
    session_path = _closed_session()
    proposal = {
        "new_decisions": [{
            "title": "Use idempotency keys",
            "body": "**Decided:** keys.\n**What it means:** retries are safe.",
        }],
        "new_open_questions": [{"question": "per-currency limits?", "context": "came up mid-run", "owner": "dev"}],
        "updates_to_existing": [{"path": "02-Builder/Projects/DistillProj/Existing.md", "suggested_change": "mention keys"}],
        "discard": ["lunch chatter"],
    }

    result = apply_distillation(session_path, proposal, confirm=True)

    assert len(result["created_decisions"]) == 1
    decision = read(safe_path(result["created_decisions"][0]))
    assert f"source_episodic: {session_path}" in decision
    assert "- dev" in decision and "- ba" in decision
    assert "**Decided:** keys." in decision

    assert len(result["created_open_questions"]) == 1
    question = read(safe_path(result["created_open_questions"][0]))
    assert f"source_episodic: {session_path}" in question
    assert "owner: dev" in question

    # advisory passthrough, untouched
    assert result["updates_to_existing"] == proposal["updates_to_existing"]
    assert result["discarded"] == ["lunch chatter"]


def test_apply_distillation_marks_session_promoted(memory_roots):
    session_path = _closed_session()
    apply_distillation(session_path, {"new_decisions": []}, confirm=True)
    assert "promoted: true" in read(safe_path(session_path))
    assert distill_session(session_path)["already_promoted"] is True

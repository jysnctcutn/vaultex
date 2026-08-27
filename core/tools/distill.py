"""Distillation (Phase 3): turn a closed episodic session into durable
notes. Two tools, deliberately split so the write path can be gated:

- distill_session  -- read-only. Bundles the session + project context +
  the proposal schema for a calling agent/skill to fill. No LLM call here;
  extraction quality lives in the caller (see docs/memory-curator.md).
- apply_distillation -- writes the filled proposal into the durable store
  via save_decision / save_open_question, with provenance, then marks the
  session `promoted: true`. Opt-in: ENABLE_DISTILL_APPLY + confirm=True.

Scope: Builder projects only (episodic notes carry a project name, not a
professional flag). updates_to_existing is advisory in v1 -- returned, not
applied, since section-aware patching is still parked.
"""

from ..frontmatter import join, split
from ..mcp_app import distill_apply_tool, mcp
from ..vault import VAULT_PATH, TaxonomyNotConfigured, read, safe_path, validate_limit, write

# Shape apply_distillation expects and distill_session hands back for a
# caller to fill. Values are human-readable type hints, not a JSON Schema.
PROPOSAL_SCHEMA = {
    "new_decisions": [{
        "title": "str",
        "body": "str -- must contain '**Decided:**' and '**What it means:**'",
        "subfolder": "str | null -- required if the project has configured subfolders",
        "confidence": "float 0-1 (advisory)",
    }],
    "new_open_questions": [{
        "question": "str",
        "context": "str",
        "owner": "str -- e.g. 'dev' / 'ba' / 'human'",
    }],
    "updates_to_existing": [{
        "path": "str -- existing durable note",
        "suggested_change": "str -- advisory only in v1, not auto-applied",
    }],
    "discard": ["str -- noise not worth keeping, for the record"],
}

_TOP_LEVEL_KEYS = set(PROPOSAL_SCHEMA)


def _load_session(session_path: str):
    note_path = safe_path(session_path)
    if not note_path.is_file():
        raise FileNotFoundError(f"No such episodic note: {session_path}")
    fm, body = split(read(note_path))
    if fm.get("type") != "episodic":
        raise ValueError(f"{session_path} is not an episodic note (type={fm.get('type')!r})")
    project = fm.get("project")
    if not project:
        raise ValueError(f"{session_path} has no `project` in frontmatter; cannot distill it.")
    return note_path, fm, body, project


@mcp.tool()
def distill_session(session_path: str, limit: int = 20) -> dict:
    """Bundle everything needed to distill a (usually closed) episodic
    session into durable notes: the session note, the project's current
    durable context, its existing open questions, and the proposal schema
    to fill. Read-only -- pass the filled proposal to apply_distillation
    to write it back."""
    validate_limit(limit)
    note_path, fm, _, project = _load_session(session_path)

    from .open_questions import get_open_questions
    from .projects import get_project_context

    try:
        open_questions = get_open_questions(project, limit=limit)
    except TaxonomyNotConfigured:
        open_questions = []

    return {
        "session": {"path": str(note_path.relative_to(VAULT_PATH)), "content": read(note_path)},
        "project": project,
        "already_promoted": bool(fm.get("promoted", False)),
        "session_status": fm.get("status"),
        "project_context": get_project_context(project, professional=False, limit=limit),
        "existing_open_questions": open_questions,
        "proposal_schema": PROPOSAL_SCHEMA,
    }


def _validate_proposal(proposal: dict) -> None:
    if not isinstance(proposal, dict):
        raise ValueError("proposal must be an object with keys: " + ", ".join(sorted(_TOP_LEVEL_KEYS)))
    unknown = set(proposal) - _TOP_LEVEL_KEYS
    if unknown:
        raise ValueError(f"Unknown proposal key(s): {', '.join(sorted(unknown))}. "
                         f"Allowed: {', '.join(sorted(_TOP_LEVEL_KEYS))}.")
    for key in ("new_decisions", "new_open_questions", "updates_to_existing", "discard"):
        if key in proposal and not isinstance(proposal[key], list):
            raise ValueError(f"proposal['{key}'] must be a list.")
    for i, d in enumerate(proposal.get("new_decisions", [])):
        if not isinstance(d, dict) or not d.get("title") or not d.get("body"):
            raise ValueError(f"new_decisions[{i}] needs a non-empty 'title' and 'body'.")
    for i, q in enumerate(proposal.get("new_open_questions", [])):
        if not isinstance(q, dict) or not q.get("question"):
            raise ValueError(f"new_open_questions[{i}] needs a non-empty 'question'.")


@distill_apply_tool
def apply_distillation(session_path: str, proposal: dict, confirm: bool = False) -> dict:
    """Write a filled distillation proposal into the durable store: each
    new_decisions item via save_decision, each new_open_questions item via
    save_open_question -- both stamped with source_episodic + the session's
    agents -- then mark the session `promoted: true`.

    updates_to_existing and discard are returned untouched (advisory).
    Requires confirm=True; the tool is only registered when
    ENABLE_DISTILL_APPLY is set."""
    if not confirm:
        raise ValueError("apply_distillation makes durable writes; pass confirm=True to proceed.")
    _validate_proposal(proposal)
    note_path, fm, _, project = _load_session(session_path)
    session_rel = str(note_path.relative_to(VAULT_PATH))
    agents = fm.get("agents") or []

    from .architecture import save_decision
    from .open_questions import save_open_question

    created_decisions = [
        save_decision(d["title"], d["body"], professional=False, project_name=project,
                      subfolder=d.get("subfolder"), source_episodic=session_rel, agents=agents)
        for d in proposal.get("new_decisions", [])
    ]
    created_open_questions = [
        save_open_question(project, q["question"], q.get("context", ""),
                           source_episodic=session_rel, owner=q.get("owner", "human"))
        for q in proposal.get("new_open_questions", [])
    ]

    fm2, body2 = split(read(note_path))
    fm2["promoted"] = True
    write(note_path, join(fm2, body2), overwrite=True)

    return {
        "session_marked_promoted": session_rel,
        "created_decisions": created_decisions,
        "created_open_questions": created_open_questions,
        "updates_to_existing": proposal.get("updates_to_existing", []),
        "discarded": proposal.get("discard", []),
    }

#!/usr/bin/env python3
"""Reproducible benchmark: gathering project context in a *new* AI client
session by hand (find the right notes, open each, copy the content) vs. one
`get_architecture_context` tool call.

This does not measure time or tokens saved on the content itself — the
content transferred is the same either way, the AI still has to read it.
What it measures is real, structural: how many manual find-and-copy actions
a human has to perform per context handover, and how that scales once the
same handover repeats across multiple AI clients (Claude Desktop, ChatGPT,
Claude Code, a phone session, ...) that don't share memory with each other.

Nothing here touches your real vault or taxonomy.json. It builds a throwaway
synthetic vault in a temp directory (fake "Acme" project, not real data),
copies the actual core/ package against it, and calls the real tool
function — so the numbers reflect the real code path, not a hand-wave.

Run: python3 benchmarks/context_handover_benchmark.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Synthetic vault content — representative note lengths for an active
# project (a few hundred words each), not real personal or client data.
FIXTURE_NOTES = {
    "02-Professional/Projects/Acme-Redesign/Overview.md": textwrap.dedent("""\
        # Acme Redesign — Overview

        Rebuilding Acme's internal ops dashboard on top of the new event
        pipeline. Goal is to cut the time between an event landing and it
        showing up in the dashboard from ~15 minutes to under 30 seconds,
        and to remove the nightly batch job that currently reconciles
        yesterday's numbers by hand.

        Stakeholders: ops team (primary users), data platform team (owns
        the event pipeline), and the on-call rotation that currently pages
        someone every time the batch job fails silently.

        Scope for v1: read-only dashboard, three core views (throughput,
        error rate, queue depth), no write-back into the pipeline. Write
        actions (retry, pause, drain) are explicitly out of scope until v2,
        once the read path has been stable in production for a full
        quarter.

        Constraints: must run inside the existing VPC, no new managed
        services without a cost review, and the dashboard has to degrade
        gracefully (stale-but-labeled data) if the event stream itself is
        down, since that's exactly when ops needs it most.
        """),
    "02-Professional/Projects/Acme-Redesign/Requirements.md": textwrap.dedent("""\
        # Acme Redesign — Requirements

        ## Functional
        - Live throughput view, updates within 30s of an event landing.
        - Error-rate view broken down by event type and by upstream
          service, last 24h rolling window.
        - Queue-depth view per topic, with a configurable alert threshold
          per topic (ops sets their own, not hardcoded).
        - Historical drill-down: pick any 1h window in the last 30 days and
          see the same three views reconstructed from stored aggregates.

        ## Non-functional
        - Dashboard must load in under 2s on a cold cache.
        - No PII in any view — event payloads get redacted at ingestion,
          not at display time, so a dashboard bug can't leak anything the
          pipeline already stripped.
        - Read path must survive the event pipeline being fully down: show
          last-known values, clearly labeled as stale, not a blank screen.

        ## Explicitly out of scope for v1
        - Any write/control actions against the pipeline.
        - Multi-tenant support — this is Acme-internal only for now.
        """),
    "02-Professional/Projects/Acme-Redesign/Notes - Kickoff call.md": textwrap.dedent("""\
        # Kickoff call notes

        Attendees: ops lead, data platform lead, me.

        Ops lead's biggest pain point isn't the dashboard itself, it's that
        nobody trusts the numbers right now — the nightly batch job has
        silently dropped rows twice this quarter and nobody noticed for
        days. So "trustworthy" matters more than "pretty" for v1.

        Data platform lead flagged that the event pipeline's schema is
        mid-migration (old and new event shapes coexist for ~6 more weeks).
        Dashboard needs to handle both shapes without ops having to know
        which one they're looking at.

        Agreed next step: I write up a short options doc on where to read
        from (subscribe directly to the topic vs. a materialized read
        replica) before committing to an architecture.
        """),
    "02-Professional/Tech-Analysis/Acme-Redesign - Read path options.md": textwrap.dedent("""\
        # Acme Redesign — read path options

        Comparing two ways for the dashboard to get data out of the event
        pipeline.

        **Option A — subscribe directly to the topic.** Lowest latency,
        but the dashboard process now has to do its own aggregation and
        hold state, and every dashboard replica re-does that work
        independently unless we add a shared cache.

        **Option B — materialized read replica, dashboard queries it.**
        Aggregation happens once, dashboard stays stateless, but adds a
        replication hop (~1-3s lag) and one more moving part to keep
        healthy.

        Recommendation: Option B. The 30s freshness requirement has slack
        for a few seconds of replication lag, and "one more moving part"
        is a smaller operational cost than every dashboard replica
        maintaining its own aggregation state correctly during the schema
        migration mentioned in the kickoff notes.
        """),
    "02-Professional/Tech-Analysis/Acme-Redesign - Alerting library.md": textwrap.dedent("""\
        # Acme Redesign — alerting library options

        Ops wants per-topic queue-depth thresholds they can set themselves,
        not hardcoded. Short-listed two approaches: build a small rules
        table + polling check ourselves, vs. wiring the existing company
        alerting service (already used by three other internal tools) into
        the new dashboard.

        Leaning toward the existing alerting service — it already has
        on-call routing and a UI ops is familiar with, and "yet another
        place to check for alerts" was explicitly called out as a
        complaint in the kickoff call.
        """),
    "02-Professional/Architecture/Acme-Redesign - System diagram notes.md": textwrap.dedent("""\
        # Acme Redesign — architecture notes

        Event pipeline --> materialized read replica (Option B from the
        read-path doc) --> dashboard API (stateless) --> dashboard UI.

        Alert thresholds live in the existing company alerting service
        (see alerting-library doc), which polls the same read replica
        rather than the raw topic, so alerting and dashboard numbers never
        disagree with each other.

        Staleness handling: dashboard API tags every response with the
        replica's last-write timestamp; UI shows a "data as of Xs ago"
        banner and switches to a stale-data visual state past 60s.
        """),
    # Unrelated notes in the *same* folders — included so the benchmark
    # also checks that the tool correctly filters to the one project
    # instead of a human having to eyeball filenames themselves.
    "02-Professional/Tech-Analysis/Other-Client - Caching layer.md": textwrap.dedent("""\
        # Other-Client — caching layer options

        Unrelated tech-analysis note for a different project, sitting in
        the same folder. Exists in this fixture only to prove that
        get_architecture_context() filters by project name
        instead of returning everything in the folder.
        """),
    "02-Professional/Architecture/Other-Client - Network diagram.md": textwrap.dedent("""\
        # Other-Client — network diagram

        Unrelated architecture note for a different project, same
        folder-filtering purpose as the tech-analysis one above.
        """),
}

TAXONOMY = {
    "roles": {
        "professional_projects": "02-Professional/Projects",
        "tech_analysis": "02-Professional/Tech-Analysis",
        "architecture": "02-Professional/Architecture",
        "decisions": "02-Professional/Decisions",
        "ideas": None,
        "builder_projects": None,
        "inbox": None,
    },
    "custom_categories": [],
}

RUNNER_SCRIPT = textwrap.dedent("""\
    import json
    from core.tools.architecture import get_architecture_context
    from core.vault import (
        PROFESSIONAL_ARCHITECTURE,
        PROFESSIONAL_PROJECTS,
        PROFESSIONAL_TECH_ANALYSIS,
        iter_markdown,
    )

    PROJECT = "Acme-Redesign"

    # What the tool actually returns via one call.
    result = get_architecture_context(PROJECT)
    tool_notes = [n for group in result.values() for n in group]

    # Ground truth for what a human would have to manually track down across
    # three separate folders to reconstruct the same context by hand,
    # including the unrelated notes they'd have to *notice and skip*.
    all_tech_analysis = list(iter_markdown(PROFESSIONAL_TECH_ANALYSIS))
    all_architecture = list(iter_markdown(PROFESSIONAL_ARCHITECTURE))
    all_project_notes = list(iter_markdown(PROFESSIONAL_PROJECTS / PROJECT))

    matching_tech_analysis = [p for p in all_tech_analysis if PROJECT.lower() in p.name.lower()]
    matching_architecture = [p for p in all_architecture if PROJECT.lower() in p.name.lower()]

    manual_relevant_files = all_project_notes + matching_tech_analysis + matching_architecture
    manual_distractor_files = (
        [p for p in all_tech_analysis if p not in matching_tech_analysis]
        + [p for p in all_architecture if p not in matching_architecture]
    )

    print(json.dumps({
        "vaultex_tool_calls": 1,
        "vaultex_folders_caller_needs_to_know": 0,
        "notes_assembled_by_tool": len(tool_notes),
        "chars_assembled_by_tool": sum(len(n["content"]) for n in tool_notes),
        "manual_folders_human_must_search": 3,
        "manual_relevant_files_to_open_and_copy": len(manual_relevant_files),
        "manual_distractor_files_present_in_same_folders": len(manual_distractor_files),
    }, indent=2))
""")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        bench_repo = tmp / "repo"
        shutil.copytree(REPO_ROOT / "core", bench_repo / "core")
        vault = tmp / "vault"
        for rel_path, content in FIXTURE_NOTES.items():
            note_path = vault / rel_path
            note_path.parent.mkdir(parents=True, exist_ok=True)
            note_path.write_text(content, encoding="utf-8")

        (bench_repo / "taxonomy.json").write_text(json.dumps(TAXONOMY, indent=2), encoding="utf-8")
        (bench_repo / "_runner.py").write_text(RUNNER_SCRIPT, encoding="utf-8")

        env = os.environ.copy()
        env["VAULTEX_PATH"] = str(vault)
        env["MCP_AUTH_TOKEN"] = "benchmark-fixture-not-a-real-secret"  # noqa: S105
        env.pop("OAUTH_ISSUER_URL", None)
        env.pop("AUTHORIZE_PASSWORD", None)

        result = subprocess.run(
            [sys.executable, "_runner.py"],
            cwd=bench_repo,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            sys.exit(result.returncode)

        stats = json.loads(result.stdout)

    print("Single handover (one project, one new client session):")
    print(json.dumps(stats, indent=2))

    print("\nScaling across clients that don't share context with each other")
    print("(e.g. Claude Desktop, ChatGPT, Claude Code, a phone session):")
    print(f"{'clients':>8} | {'manual file-copies':>19} | {'vaultex tool calls':>19}")
    for clients in (1, 2, 3, 5):
        manual = clients * stats["manual_relevant_files_to_open_and_copy"]
        vaultex = clients * stats["vaultex_tool_calls"]
        print(f"{clients:>8} | {manual:>19} | {vaultex:>19}")


if __name__ == "__main__":
    main()

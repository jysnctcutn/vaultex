# Manual context handover vs. one tool call

[← Back to README](../README.md) · [Docs index](README.md)

Easy to *claim* this beats copy-pasting between AI clients; here's a
measurement instead of a marketing number.

**The scenario**: you close a chat in one AI client and open a different
one — Claude Desktop today, Claude Code tomorrow, ChatGPT or Claude on your
phone next week. None of them share memory with each other. Without
Vaultex, reconstructing "what were we doing on this project" means manually
finding and pasting in the relevant notes, every time you switch.

[`benchmarks/context_handover_benchmark.py`](../benchmarks/context_handover_benchmark.py)
measures this directly instead of guessing a percentage. It builds a
synthetic vault (fake "Acme-Redesign" project, not real data) with notes
spread across three folders the way a real Solution-Architecture project
actually accumulates them — project notes, tech-analysis notes, architecture
notes — plus two unrelated notes sitting in those same folders, to check
that filtering by project actually works rather than just counting files.
It then runs the real `get_solution_architecture_context()` tool code
against that fixture — not a simulation of it. Reproduce it yourself:

```bash
python3 benchmarks/context_handover_benchmark.py
```

Measured result for that fixture, one handover:

| | Manual (open + copy each note) | Vaultex |
|---|---|---|
| Folders you need to know about | 3 | 0 — resolved from `taxonomy.json` |
| Files to individually open and paste | 6 | 0 |
| Unrelated notes you must notice and skip | 2 | 0 — filtered automatically by project name |
| Round-trips to reassemble context | — | 1 |

That gap repeats every time you switch clients without shared memory:

| Clients used across a week | Manual file-copies | Vaultex tool calls |
|---|---|---|
| 1 | 6 | 1 |
| 2 | 12 | 2 |
| 3 | 18 | 3 |
| 5 | 30 | 5 |

This is not a token or speed benchmark — the AI reads the same content
either way. What it removes is the manual labor of finding and re-pasting
that content, and the chance of missing or misfiling a note, not the
reading itself. The ratio (files-per-project vs. 1 tool call) will vary
with how many notes your own projects accumulate; rerun the script against
your own taxonomy shape to get your own numbers.

# Governance

Vaultex is led by a maintainer and a co-maintainer, both with standing
repository access. This document describes how decisions get made today,
and how that's expected to change if the project grows a wider contributor
base.

## Roles

- **Maintainer** ([@jysnctcutn](https://github.com/jysnctcutn)) — has final
  say on design decisions, reviews and merges pull requests, cuts releases,
  and triages issues.
- **Co-maintainer** ([@jcapplegh](https://github.com/jcapplegh)) — has
  write access to the repository so the project can keep accepting changes,
  triaging issues, and cutting releases if the primary maintainer becomes
  unavailable. Not currently involved in day-to-day design decisions; the
  role exists to guarantee project continuity, on top of whatever else it
  grows into.
- **Contributors** — anyone who opens an issue or pull request. See
  [CONTRIBUTING.md](CONTRIBUTING.md) for the process and acceptance
  requirements.

## Decision-making

For now, this is a benevolent-maintainer model: the maintainer decides.
There's no voting process because there's no second maintainer making
design calls day-to-day — that's an honest description of the project's
current size, not an aspiration to stay closed to input. Design discussions
happen in the open, on GitHub Issues and pull requests; anyone can weigh
in, and significant decisions get a documented rationale (in commit
messages, PR descriptions, or [SECURITY.md](SECURITY.md)/[README.md](README.md)
where relevant) rather than being made silently.

If the co-maintainer becomes active in day-to-day design decisions, or the
project gains additional maintainers, this document will be updated to
describe how decisions get made among them (e.g. lazy consensus, a simple
majority among maintainers) before that becomes necessary in practice, not
after a disagreement forces the question.

## Becoming a maintainer

There's no formal process yet, because there's no track record of
contributors to draw one from. In practice: sustained, high-quality
contributions (code, review, triage) are how anyone would earn commit
access, at the current maintainer's discretion. This will get more formal
as the contributor base grows.

## Project continuity

The project's primary continuity guarantee is the co-maintainer
([@jcapplegh](https://github.com/jcapplegh)), who holds write access to
the repository: if the primary maintainer dies, is incapacitated, or is
otherwise unable or unwilling to continue, the co-maintainer can create
and close issues, accept proposed changes, and cut releases directly,
with no handoff delay.

As a secondary fallback, Vaultex is also MIT-licensed specifically so the
project isn't dependent on any one person to remain usable: anyone can
fork and continue it, with no permission needed, even if both maintainers
become unavailable.

## Changing this document

Governance changes are proposed the same way any other change is: a pull
request against this file, with the rationale in the PR description.

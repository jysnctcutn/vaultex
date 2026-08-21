# Governance

Vaultex is currently maintained by a single maintainer. This document
describes how decisions get made today, and how that's expected to change
if the project grows a real contributor base.

## Roles

- **Maintainer** ([@jysnctcutn](https://github.com/jysnctcutn)) — has final
  say on design decisions, reviews and merges pull requests, cuts releases,
  and triages issues. Currently the only person with write access to the
  repository.
- **Contributors** — anyone who opens an issue or pull request. See
  [CONTRIBUTING.md](CONTRIBUTING.md) for the process and acceptance
  requirements.

## Decision-making

For now, this is a benevolent-maintainer model: the maintainer decides.
There's no voting process because there's no second maintainer to vote
against — that's an honest description of the project's current size, not
an aspiration to stay closed to input. Design discussions happen in the
open, on GitHub Issues and pull requests; anyone can weigh in, and
significant decisions get a documented rationale (in commit messages, PR
descriptions, or [SECURITY.md](SECURITY.md)/[README.md](README.md) where
relevant) rather than being made silently.

If the project gains additional maintainers, this document will be updated
to describe how decisions get made among them (e.g. lazy consensus, a
simple majority among maintainers) before that becomes necessary in
practice, not after a disagreement forces the question.

## Becoming a maintainer

There's no formal process yet, because there's no track record of
contributors to draw one from. In practice: sustained, high-quality
contributions (code, review, triage) are how anyone would earn commit
access, at the current maintainer's discretion. This will get more formal
as the contributor base grows.

## Project continuity

Vaultex is MIT-licensed specifically so the project isn't dependent on any
one person to remain usable: anyone can fork and continue it, with no
permission needed, if the maintainer becomes unavailable. That's the
project's baseline continuity guarantee today. As the contributor base
grows, the intent is to name a backup maintainer with standing repository
access, rather than relying on the license alone — this document will be
updated once that happens.

## Changing this document

Governance changes are proposed the same way any other change is: a pull
request against this file, with the rationale in the PR description.

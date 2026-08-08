# GIC Lab

GIC Lab is a public, reproducible research program for determining which proposed mechanisms in the Goal–Identity–Configurator (GIC) architecture are necessary, sufficient, learnable, and measurably better than matched external orchestration.

The repository has completed **Phase 0.5: reading reconciliation** and opened
**Phase 0.75: upstream audit, experiment harness, and protocol lock**. Phase 0.75 is
active and permits static upstream audits, non-executing harness construction, and
protocol lock. No prototype result has been reproduced, and no model, API, benchmark,
training, cloud, or paid-compute run is authorized.

- [Public research notebook](https://abbudjoe.github.io/gic-lab/)
- [GitHub repository](https://github.com/abbudjoe/gic-lab)

## Start here

- [Project charter](docs/PROJECT_CHARTER.md)
- [Research questions](docs/RESEARCH_QUESTIONS.md)
- [Claim matrix](docs/CLAIM_MATRIX.md)
- [Falsification notes](docs/FALSIFICATION_NOTES.md)
- [Active Phase 0.75 plan](docs/exec-plans/active/PHASE_0_75_UPSTREAM_AUDIT_HARNESS_PROTOCOL_LOCK.md)
- [Completed Phase 0.5 ledger](docs/exec-plans/completed/PHASE_0_5_RECONCILIATION.md)
- [Reproducibility contract](docs/REPRODUCIBILITY.md)
- [Public notebook source](notebook/index.qmd)

## Local development

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), GNU Make, and [Quarto](https://quarto.org/).

```bash
make setup
make check
```

`make check` is the local/CI parity gate: formatting, linting, typing, tests, schema/manifests/workflow/hygiene validation, and a real Quarto render.

## Status semantics

Experiments track three independent dimensions:

- lifecycle: whether work is planned, running, completed, cancelled, or blocked;
- evidence: whether evidence is absent, preliminary, replicated, confirmed, inconclusive, contradicted, or retracted;
- outcome: whether the registered hypothesis remains pending, is supported, not supported, mixed, or invalidated.

This separation prevents “completed” from being mistaken for “confirmed,” or “failed infrastructure” from being mistaken for a negative scientific result.

`confirmed` means that evidence met a predeclared confirmatory contract for its stated scope. It is not a claim of universal truth.

## License

The repository's final software and content licenses are intentionally undecided. No reuse permission is granted for repository-authored material until licenses are added; see [Open Questions](docs/OPEN_QUESTIONS.md).

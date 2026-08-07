# GIC Lab

GIC Lab is a public, reproducible research program for determining which proposed mechanisms in the Goal–Identity–Configurator (GIC) architecture are necessary, sufficient, learnable, and measurably better than matched external orchestration.

The repository is currently in **Phase 0: research bootstrap**. No prototype result has been reproduced, and no benchmark or training run has been performed.

## Start here

- [Project charter](docs/PROJECT_CHARTER.md)
- [Research questions](docs/RESEARCH_QUESTIONS.md)
- [Claim matrix](docs/CLAIM_MATRIX.md)
- [Falsification notes](docs/FALSIFICATION_NOTES.md)
- [Active Phase 0 plan](docs/exec-plans/active/PHASE_0_BOOTSTRAP.md)
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

The repository's final software and content licenses are intentionally undecided. See [Open Questions](docs/OPEN_QUESTIONS.md) before reusing repository-authored material.

# GIC Lab Operating Rules

This repository is a public, reproducible research program for testing claims associated with GIC, SiRA, and SR²AM. Fix root causes, make hidden contracts explicit, and preserve traceable provenance.

## Repository map

- `docs/`: charter, research claims, policies, handoffs, reading notes, and execution plans.
- `experiments/`: registry and one versioned directory per experiment.
- `schemas/`: machine-readable contracts for experiments, artifacts, and transitions.
- `manifests/`: pinned sources and versioned model, dataset, artifact, and compute records.
- `notebook/`: source for the public Quarto lab notebook.
- `src/giclab/`: validation and registry tooling.
- `tests/`: contract and validation tests.

## Two authority planes

Do not merge governance authority with scientific evidence authority.

Instruction/control precedence is: current user instructions; this file and repository safety policies; the approved project charter and decision log; the active execution plan; approved experiment protocols/configurations; implementation and tests. `docs/PLANS.md` governs significant work.

Scientific-evidence precedence is: pinned primary sources and observed raw evidence; versioned protocols/configurations/manifests; validated result summaries and analyses; public notebook interpretation; historical handoffs and conversations. Project decisions cannot rewrite source claims, and source claims cannot override safety or compute policy.

## Commands

- Setup: `make setup`
- Generate the concise agent state capsule: `make state-capsule`
- Run deterministic agent/control gates: `make agent-check`
- Format: `make format`
- Lint: `make lint`
- Type-check: `make typecheck`
- Test: `make test`
- Validate repository contracts: `make validate`
- Build the site: `make site`
- Run every local/CI gate: `make check`

## Agent orientation before significant work

1. Generate and read the state capsule.
2. Identify the terminal goal, current subgoal, blocker, authority state, live-resource
   state, uncertainties, and permitted actions.
3. Run `make agent-check` before control-plane or execution work.
4. Do not infer current state or authority from historical handoffs alone.

The capsule is an orientation surface, not authority. Current-turn authorization is
external and cannot be created or inferred from Git, a plan, a receipt, or a passing
check.

## Inviolable research rules

- Never fabricate, backfill, or imply an experimental result. “Not run” is a valid state.
- Cite primary sources for scientific claims, with version and page/section/equation/figure references when available.
- Keep lifecycle state, evidence strength, and result outcome as separate typed fields.
- Version every experiment protocol/configuration and every compute-use record before interpreting results.
- Record unknown hashes, commits, licenses, and measurements as unknown; never invent provenance.
- Put large datasets, checkpoints, traces, screenshots, and optimizer state outside Git; commit manifests, hashes, and summaries instead.
- Never commit credentials. Follow `docs/SECURITY_AND_SECRETS.md`.
- Cloud/job inspection is allowed. Launching, stopping, resizing, restarting, deleting, or otherwise mutating paid compute requires explicit authorization in the current user turn and compliance with `docs/COMPUTE_POLICY.md`.
- Phase 0 must not run SiRA, SR²AM, benchmarks, training, or paid GPU compute.

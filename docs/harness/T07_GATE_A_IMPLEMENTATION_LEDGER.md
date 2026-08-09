# T07 Gate A implementation ledger

## Contract

- Governing task contract: T07 v1.2 Gate A prompt attached to the 2026-08-08 task.
- Governing readiness contract: `docs/readiness/PHASE_1_SMOKE_READINESS.md`.
- Baseline commit: `365ce0066db58f394086f306e38eacc714945e82`.
- Working branch: `phase-1/sira-smoke`.
- Scope: implementation and deterministic local validation only.
- Live execution, model/API availability requests, experimental browser use, SiRA
  installation, Playwright Chromium installation, and secret-value access are
  prohibited in this gate.

## Definition of done

| ID | Obligation | Evidence target | Status |
|---|---|---|---|
| T07-GA-DOD-01 | Route every SiRA model role and fallback to `gpt-4o-2024-11-20`; reject aliases, fallback, and mixed identities. | Repository-owned versioned adaptation plus positive and negative tests. | met |
| T07-GA-DOD-02 | Put every provider attempt, including retries, through one preflight-and-reconcile budget boundary. | Finite aggregate and condition cost/token/call/wall ceilings; fake-provider tests only. | met: durable pre-send worst-case accounting and `n`-aware reservations |
| T07-GA-DOD-03 | Enforce finite browser-action and output-byte ceilings. | Command/runtime projection and deterministic quota tests. | met |
| T07-GA-DOD-04 | Allocate a fresh immutable attempt root before launch and retain all source, command, environment, normalized, evaluator, and cleanup evidence there. | Attempt-layout contract and collision/ownership tests. | met |
| T07-GA-DOD-05 | Keep the pinned SiRA checkout clean and bind an external Python environment and owned Playwright cache without installing them. | Environment-installation contract, identity schema, and isolation tests. | met |
| T07-GA-DOD-06 | Supervise the complete process group, bound TERM/KILL escalation, verify zero live descendants, and retain cleanup evidence. | Synthetic process-tree tests; no browser or model use. | blocked: polling cannot prove an escaped/reparented child; Gate A preflight now fails closed pending kernel containment |
| T07-GA-DOD-07 | Materialize a future authorization that binds the clean GIC Lab commit, exact plan/source/environment/command identities, parent profile, and sealed children. | Unauthorized materialization API and canonical-child rejection tests. | met |
| T07-GA-DOD-08 | Restrict authorization to `PLAN-EXP0001-SMOKE` and preserve all benchmark, training, cloud, pilot, and interpretation prohibitions. | Typed authorization-policy tests and packet. | met |
| T07-GA-DOD-09 | Produce a machine-readable condition comparison permitting only declared treatment-owned differences. | Reviewed diff artifact and positive/negative tests. | met |
| T07-GA-DOD-10 | Accept only the secret name `SIRA_API_KEY`; reject fallback/inheritance and prevent secret material in serialized surfaces or evidence. | Static contract and synthetic secret-handling tests without reading a real value. | met |
| T07-GA-DOD-11 | Pass focused tests, repository validation, and pre-review `make check`. | Command log in this ledger and packet. | met |
| T07-GA-DOD-12 | Complete independent spec-conformance review, repair all valid findings, rereview clean, and pass post-review `make check`. | Reviewer findings and post-review command log. | blocked by T07-GA-DOD-06; rereview correctly failed closed |
| T07-GA-DOD-13 | Regenerate the preauthorization packet with the exact clean implementation commit, hashes, caps, pending installs, commands, cleanup, blockers, and authorization block. | `docs/harness/T07_PREAUTHORIZATION_PACKET.md`. | in progress: blocked packet prepared; exact commit pending |
| T07-GA-DOD-14 | Commit all Gate A implementation and reviewed evidence on the named T07 branch without executing the smoke. | Clean named-branch commit and zero-execution statement. | not started |

## Validation and review log

- Branch preflight: clean baseline `365ce0066db58f394086f306e38eacc714945e82`
  attached to `phase-1/sira-smoke` before implementation.
- Focused Gate A, adapter, executor, budget, and policy tests: passed.
- Repository validation: passed.
- Pre-review full `make check`: passed with 309 tests and the pinned temporary Quarto
  1.9.38 binary; no repository, SiRA, or browser installation was performed by Quarto.
- First independent spec-conformance review: failed with ten findings. All findings
  were repaired: failed sends are conservatively charged; replacement attempts require
  new authorization; all process-created attempt files share the output monitor;
  source-shaped all-role routing is tested offline; clean-commit/project-state binding
  is enforced; escaped descendants are tracked; the legacy alias contract is restored;
  and the uv cache plus `--extra eval` action are explicit.
- Repair validation: focused tests and mypy passed; full `make check` passed with 313
  tests and the same temporary Quarto binary.
- Independent rereview: failed. It found `n=20` under-reservation, non-durable and
  concurrently racy ledgers, output-monitor finalization/atomic-replace/physical-cap
  gaps, and polling-racy escaped descendants. The first three classes were repaired
  with regressions. Complete descendant containment is not available, so the Gate A
  command now carries an explicit capability requirement and preflight fails closed.
- Final independent audit confirmed the provider and output repairs closed and the
  descendant capability check effective before attempt allocation or launch. The
  remaining blocker is intentional and explicit. The final full `make check` passed
  with 316 tests and the same temporary Quarto binary.

## Gate result

Gate A is blocked at T07-GA-DOD-06. Provider accounting, output enforcement, and the
other first/rereview repairs are implemented, but live authorization cannot proceed
until a kernel-enforced descendant container is implemented and rereviewed. Commit
closeout and exact blocked-packet commit insertion remain. Live execution remains
unauthorized.

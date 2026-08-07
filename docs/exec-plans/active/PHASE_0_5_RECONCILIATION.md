# Phase 0.5 — GIC Reading Reconciliation

Status: **successful**

Started: 2026-08-06

## Source contract

The authoritative user instruction is “proceed with reconciliation,” following completion of the four-pass human reading in `docs/reading/GIC_HUMAN_READING_TEMPLATE.md`. Scientific claims must resolve against the hash-pinned `SRC-GIC-PAPER` in `manifests/sources.yaml`, not against either draft by authority.

## Target contract

Reconcile the independent human reading and agent extraction into a source-grounded claim set. Preserve genuine disagreements, distinguish paper statements from project hypotheses, and close the reading gate without approving a Phase 1 experiment or consuming compute.

## Scope

In scope: source hash verification; claim crosswalk; primary-source resolution; theorem/mechanism separation; reconciliation records; claim-status updates; canonical claim-matrix updates; reading-gate decisions; deterministic local validation and independent review.

Out of scope: selecting or approving the Phase 1 primary hypothesis; running prototypes or benchmarks; downloading checkpoints; training; paid compute; cloud mutation; resolving repository publication identity, hosting, or licenses.

## Definition of done ledger

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| R-DOD-01 | The exact pinned GIC PDF is verified against the manifest hash and used as the primary source. | SHA-256, byte size, title, author, and page-count check. | met |
| R-DOD-02 | Every agent claim is mapped to one or more human claims, including claims missing from either draft. | Crosswalk in the human reconciliation record and reconciled agent draft. | met |
| R-DOD-03 | Every material disagreement is resolved from exact source locations or retained as an explicit open ambiguity. | Reconciliation rows with source resolution and decision status. | met |
| R-DOD-04 | Conditional theorems remain separate from empirical applicability claims, and duplicate theorem coverage is removed. | Reconciled human claim and falsification matrices. | met |
| R-DOD-05 | The canonical claim matrix reflects the reconciled GIC source reading and does not imply local reproduction. | Updated `docs/CLAIM_MATRIX.md` with source boundaries. | met |
| R-DOD-06 | Reading artifacts have final reconciliation statuses and preserve unresolved questions needed before Phase 1. | Status fields, decisions, and `docs/OPEN_QUESTIONS.md`. | met |
| R-DOD-07 | Repository validation, tests, source checks, independent spec-conformance review, and post-review smoke pass. | Command evidence and reviewer classification. | met |

## Implementation mapping

| Work package | Mapped DoD |
|---|---|
| Hash-verified primary-source audit | R-DOD-01, R-DOD-03 |
| Human/agent crosswalk and claim repairs | R-DOD-02, R-DOD-03, R-DOD-04 |
| Canonical claim and open-question projection | R-DOD-05, R-DOD-06 |
| Smoke, independent review, fixes, rerun, and closeout | R-DOD-07 and all mapped items |

## Success criterion

All agent and human claims have a documented disposition; no duplicate theorem claim remains; source ambiguities are explicit; the canonical matrix is source-grounded; validation and independent review pass; no Phase 1 protocol or empirical result is approved or claimed.

## Progress log

- 2026-08-06: Entered the reconciliation workstream after the user completed the human reading and authorized reconciliation.
- 2026-08-06: Read the Assembly and repository plan contracts; confirmed that no cloud, GPU, prototype, benchmark, or training action is in scope.
- 2026-08-06: Retrieved `arXiv:2606.23991v1` into temporary storage. Its SHA-256 (`3abe1e5cbad9aac107f93dc269237ddf772879bcb55661f10735422805895454`), size (1,197,188 bytes), title, authors, and 44-page count match the manifest.
- 2026-08-06: Began primary-source comparison across §§2, 4, 5 and Appendices A–D.
- 2026-08-06: The pre-review `make check` reached repository tests and failed because project-state validation hard-coded Phase 0. Replaced that hidden phase contract with typed decimal phase, assembly-status, pre-Phase-1 authorization, authoritative-plan heading, and plan-status consistency checks; added regression tests.
- 2026-08-06: A focused test then exposed recurrence of the macOS hidden editable-`.pth` failure previously seen in Phase 0. Changed the canonical sync to a non-editable wheel installation, eliminating dependence on generated `.pth` discovery rather than adding another flag-clearing workaround.
- 2026-08-06: The next clean site attempt showed that plain `uv run` auto-synchronized and silently replaced the wheel with an editable install. Made `sync` the sole environment owner and changed all Makefile execution gates to `uv run --no-sync`.
- 2026-08-06: Wheel-based tests then exposed that repository root was derived from `__file__`, another editable-install assumption. Added marker-based root discovery from the working directory with package-location fallback and a nested-path regression test.
- 2026-08-06: Completed the 16-to-21 claim crosswalk, populated twelve reconciliation decisions, updated the canonical 21-claim GIC matrix plus companion boundaries, and recorded four source/implementation ambiguities for Phase 1 design.
- 2026-08-06: The complete pre-review gate passed after the control-plane fixes: 19 tests, strict type checking, repository validation, 13-page Quarto render, and rendered-site validation.
- 2026-08-06: Independent review found two source-boundary issues and a project-state validation defect. Removed an unsupported episodic-memory distinction from the paper claim, deferred critic ownership to OQ-014, rejected nonfinite phases, and converted escaping plan paths into validation errors.
- 2026-08-06: Independent rereview found no remaining actionable issues. The complete post-review gate passed with 23 tests, strict type checking, repository validation, a 13-page Quarto render, and rendered-site validation.

## Decision log

- 2026-08-06: Treat the paper, human reading, and agent extraction as three distinct evidence roles: primary source, independent interpretation, and provisional extraction. Neither interpretation overrides the paper.
- 2026-08-06: Use the human matrix's theorem/mechanism separation as the canonical granularity, while restoring source claims the agent draft captured but the human matrix did not isolate.
- 2026-08-06: Do not treat a paper-level architectural assertion as a locally demonstrated result.
- 2026-08-06: Project state is phase-relative runtime state, not a permanent assertion that the repository can only be in Phase 0.
- 2026-08-06: The validation environment uses a non-editable local package install because its contract is deterministic importability, not live source mutation.
- 2026-08-06: Validation commands may not mutate or reinterpret the environment after the canonical sync step.

## Evidence log

- Source verification: `shasum -a 256`, `stat`, and `pdfinfo` on the temporary pinned PDF — **passed** and matched `manifests/sources.yaml`.
- Source inspection: hash-verified PDF pp. 4–8, 11–22, 24–31, and 37–44 — **completed** for the claims under reconciliation.
- Initial pre-review gate: `make check` — **smoke-failed** at `test_repository_contract_passes`; the validator incorrectly required project phase `0`.
- Focused recovery test after the state-validator fix — **smoke-failed during collection** because the generated editable `.pth` reacquired the macOS hidden flag and `giclab` became unimportable.
- First clean site recovery — **smoke-failed** because `uv run` auto-sync restored the editable install before the site generator started.
- First no-sync full gate — **smoke-failed** because installed-wheel code derived the repository root from `site-packages` rather than explicit project markers.
- Pre-review gate: `make check` — **passed**; formatting and linting clean, strict mypy clean, 19 tests passed, repository validation passed, 13 Quarto pages rendered, and rendered-site validation passed.
- Visual source check: rendered PDF pp. 16, 26, 30, 41, and 44 — **passed** against the reconciled theorem, factorization, separation, terminal-goal, auditability, safety, and non-inferiority wording.
- Independent spec-conformance review — **review-failed initially** on two scientific-boundary issues and one validator robustness defect; all findings were accepted and corrected.
- Focused recovery gate: `PYTHONPATH=src .venv/bin/pytest tests/test_validation.py -q`, `PYTHONPATH=src .venv/bin/mypy`, and `PYTHONPATH=src .venv/bin/ruff check src/giclab/validation.py tests/test_validation.py` — **passed**; 17 focused tests plus strict typing and linting.
- Independent rereview — **passed**; no actionable findings remained, and R-DOD-01 through R-DOD-06 were independently classified met.
- Post-review gate: `make check` — **passed**; lock and noneditable install clean, formatting and linting clean, strict mypy clean, 23 tests passed, repository validation passed, 13 Quarto pages rendered, and rendered-site validation passed.

## Outcome and retrospective

Phase 0.5 closed successfully. The reconciled record contains 21 source-grounded human claims, a complete mapping from all 16 independent agent claims, twelve disagreement dispositions, four explicit source/implementation ambiguities, and separate treatment of architectural mechanisms, conditional theorems, empirical applicability, and project governance. No prototype, benchmark, training, cloud, or paid-compute action occurred.

The reconciliation also exposed three reusable control-plane lessons: project phase must be typed without being hard-coded; environment synchronization must have one owner; and repository discovery must not depend on editable-install layout. These contracts are now enforced by validation and regression tests.

## Next permitted phase

After this reconciliation plan is successful, Phase 0.5 may recommend candidate Phase 1 hypotheses. It may not approve or execute a Phase 1 protocol without a new explicit user instruction.

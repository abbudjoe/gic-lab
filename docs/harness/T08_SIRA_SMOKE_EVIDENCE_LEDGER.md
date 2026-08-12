# T08 SiRA Smoke Evidence Adjudication — Assembly Ledger

Assembly status: **complete**

Terminal state: **`smoke_evidence_validated_pilot_planning_eligible`**

## Source and target contracts

The authoritative source contract is the user-supplied **T08 — SiRA Smoke Evidence
Adjudication and Pilot-Readiness Review** instruction dated 2026-08-12. Repository
authority is additionally constrained by `AGENTS.md`, `docs/PLANS.md`,
`docs/COMPUTE_POLICY.md`, `docs/SECURITY_AND_SECRETS.md`, and
`docs/exec-plans/active/PHASE_1_ARTIFACT_EXECUTION.md`.

The target contract is an offline, evidence-only reconstruction and adjudication of
the retained T07 pragmatic Retry 2 SiRA smoke. T08 may prepare an unauthorized pilot
package only when pair validity, smoke evidence sufficiency, and cleanup evidence pass
their declared gates. It may not execute SiRA, a browser, a model/API call, paid
compute, training, or the pilot, and it may not interpret the smoke scientifically.

Mapped Phase 1 DoD: `P1-DOD-03`, `P1-DOD-11`, `P1-DOD-12`, and `P1-DOD-13`.

## T08 definition of done

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| T08-DOD-01 | Verify the exact T08 branch, clean required start commit, offline prohibitions, and evidence roots before adjudication. | Git identity/status; policy review; local and external root inventory. | met |
| T08-DOD-02 | Independently verify every retained immutable identity and both local-to-external evidence copies without substituting turn-summary values. | SHA-256/byte rehashes; archive and external manifest validation; explicit unavailable identities. | met |
| T08-DOD-03 | Reconstruct reactive and simulative commands, configurations, runtime, model/browser activity, outputs, and cleanup with `observed`, `derived`, `inferred`, or `unavailable` provenance on every requested field. | Machine-readable adjudication and narrative reconstruction tied to raw paths/hashes. | met |
| T08-DOD-04 | Machine-compare pair invariants, permit only declared identity/treatment/realized-event differences, and emit exactly one allowed pair classification. | Recomputed pair-diff artifact plus focused tests. | met |
| T08-DOD-05 | Independently reconcile calls, tokens, service tier, attempts, pricing, costs, browser actions, and wall time, preserving any unavailable per-call evidence. | Decimal recomputation from retained ledgers; exact discrepancies and rounding record. | met |
| T08-DOD-06 | Separate artifact execution from task completion and prohibit EXP-0001 outcome or GIC/RQ-H2K scientific claims. | Typed disposition, negative-boundary tests, and public wording. | met |
| T08-DOD-07 | Inventory evidence completeness, assess H2K trace sufficiency, and adjudicate provider/runtime cleanup including privacy gaps. | Evidence ledger, trace assessment, source/destination checks, cleanup classification. | met |
| T08-DOD-08 | Emit one schema-valid T08 disposition and exactly one allowed terminal state with pilot execution unauthorized. | `T08_SMOKE_ADJUDICATION.json`, schema validation, and terminal-state assertion. | met |
| T08-DOD-09 | If the gates pass, prepare the smallest justified exploratory pilot package with frozen tasks/order, budgets, scoring, stopping, evidence, and interpretation contracts. | T09 plan, preauthorization packet, updated schema-valid `pilot.yaml`; `authorized: false`. | met |
| T08-DOD-10 | Update experiment/project/plan/decision/readiness/public surfaces without marking EXP-0001 successful or failed. | Registry/results/state/plan/decision/readiness/notebook diffs and boundary tests. | met |
| T08-DOD-11 | Pass focused evidence, hash, pair, accounting, disposition, pilot-schema, privacy, and boundary validation. | Exact focused commands and results below. | met |
| T08-DOD-12 | Obtain independent spec-conformance review, repair all material findings, rerun focused checks, then pass `make validate`, `git diff --check`, and `make check`. | Reviewer verdict, repair log, post-review commands, final clean commit. | met; clean commit is the handoff artifact |

No required T08 item may remain `partial`, `blocked`, or `not-started` at successful
closeout. A retained evidence gap is not itself an incomplete DoD item when it is
truthfully classified, nonblocking under the source contract, and carried into the
disposition and pilot preconditions.

## Starting evidence

- Branch attached: `phase-1/sira-smoke-t08-evidence`.
- Required clean starting commit:
  `27f66e6a82edffa57e497516bf3969a199675f06`.
- Frozen T07 execution commit:
  `5698f04dfd08bc85a66d2355b0a4bd7d3ce24a23`.
- Read-only local evidence root: the retained T07 worktree's ignored
  `artifacts/t07/pragmatic/RUN-T07-PRAGMATIC-HOST-0002` directory; its private
  absolute path is intentionally omitted from this public ledger.
- Read-only external sealed root: retained on the approved APFS evidence volume; its
  private absolute path is intentionally omitted from this public ledger.
- T08 working extraction: temporary and outside Git; it is not an evidence authority.

The local root was absent from the T08 worktree at start. For offline full-suite
validation, an ignored byte copy was staged from the retained source into the expected
artifact path; it is neither committed nor treated as an evidence authority. The
retained source root and external sealed copy were read without mutation.

## Progress and evidence log

- 2026-08-12: Read the complete T08 instruction and Assembly skill, mapped the work to
  Phase 1 DoD, and confirmed that no cloud or live execution is authorized.
- 2026-08-12: Confirmed the clean required commit and attached the existing T08 branch.
- 2026-08-12: Located the retained local evidence in the successful T07 worktree and
  the sealed external copy. No value from the request summary was used to fill an
  absent raw identity.
- 2026-08-12: Rehashed all 138 remote-archive manifest entries (281,235 bytes) with
  zero mismatch. Rehashed all 148 external-manifest entries and their retained local
  sources with zero mismatch.
- 2026-08-12: Identified a cleanup/privacy gap: private raw provider-response evidence
  retains an ephemeral Jupyter access credential while the historical secret scan
  covered only the Lambda and OpenAI API-key values. The instance is terminally
  absent, so the credential is inactive and no long-lived rotation is indicated. T08
  and public notebook outputs must not reproduce the value.
- 2026-08-12: Reconstructed both 24-field condition records with field-level
  provenance, including exact commands, source-resolved mode configuration, runtime,
  aggregate provider usage, session/log/screenshot evidence, T08-derived events and
  regulation records, and cleanup.
- 2026-08-12: Independently recomputed the 79-element Docker argument diff (exactly
  six approved positions) and the configuration diff (exactly four approved fields),
  then required exact object equality with the retained T07 diff records.
- 2026-08-12: Reconciled 9 calls, 10,073 input tokens, zero cached-input tokens,
  1,515 output tokens, 11,588 total tokens, two recorded browser-action requests,
  39.397491319999743 seconds, zero unreconciled attempts, and exact USD 0.0403325
  cost.
- 2026-08-12: Emitted adjudication SHA-256
  `414804e52e8ae285b8b98bfb3ca071d2342afa74387581f2779760cc9fad8ffc`
  and pair-diff SHA-256
  `e11b949c444283772de67cbac74f0e024b192266e33360331bb7617dc0dd5dba`.
  A fresh full evidence reconstruction reproduced both tracked files byte-for-byte.
- 2026-08-12: Prepared two counterbalanced FanOutQA task pairs under
  `PLAN-EXP0001-PILOT`, with explicit model-call/token/browser/wall/API/provider/
  accelerator/total caps and `authorized: false`. Execution stays
  `blocked-pending-prerequisites`.

## Review and final gates

Pre-review focused gate:

- Targeted Ruff: passed.
- Strict mypy over the adjudicator and changed control planes: passed.
- `pytest -q tests/test_t08_sira_smoke.py tests/test_exp0001_protocol.py`: 30 passed.
- Fresh raw-evidence regeneration and byte comparison: passed.
- `make validate`: passed.
- `git diff --check`: passed.

Independent review and repair loop:

- Initial independent verdict identified three material issues: pilot model-call
  limits were not child-owned typed hard caps; browser-action performance was labeled
  more strongly than the retained pre-action history allowed; and shared pair
  bindings were not distinguished from condition-owned comparisons. It also found
  stale pre-T07 public wording.
- Repairs added typed `RunBudget.max_model_calls` accounting/enforcement and exact
  parent/child reconciliation; changed the event to `requested_action`, classified
  action performance as inferred, and added a six-part provenance-bearing artifact
  execution basis; labeled each pair equality by its comparison authority; compared
  condition-owned runtime/session/image/routing/tool records directly; and repaired
  the stale public surfaces.
- The same independent reviewer regenerated both machine records byte-for-byte and
  returned **PASS — no remaining material blockers**.
- The first full-suite attempt then exposed five stale historical-fixture assumptions.
  Repairs preserved fail-closed ordering for frozen control planes, made a missing
  prospective substrate an explicit authorization-drift stop, and made the sealed
  L1.3 evidence consumer portable across worktrees while retaining exact path-suffix,
  byte, hash, and seal checks. A second independent safety rereview returned **PASS —
  no remaining material safety or regression blockers**.

Post-review focused and final gates:

- Targeted Ruff and strict mypy over the changed harness/control surfaces: passed.
- Focused evidence/control-plane suite: 233 passed.
- Fresh raw-evidence regeneration and byte comparison: passed.
- `make validate`: passed.
- `git diff --check`: passed.
- Full `make check` with the already-retained offline Quarto 1.9.38 binary: lock,
  reinstall, format/lint, 58-source-file mypy, 1,284 tests, repository validation,
  four generated public views, 16-page Quarto render, and site validation all passed.

## Next permitted work

T08 is closed. T09 remains a planning package only: close every recorded prerequisite
and obtain a new exact current-turn authorization before any pilot execution. No live
action is authorized by this ledger or terminal state.

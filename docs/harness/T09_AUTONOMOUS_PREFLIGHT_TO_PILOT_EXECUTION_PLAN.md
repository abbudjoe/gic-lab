# T09 Autonomous Preflight-to-Pilot Execution Plan

Status: **in-progress**

Source contract: the current-turn user instruction, `T09 Autonomous
Preflight-to-Pilot Reset`, SHA-256
`80ded0e246b4f070c3992ae872111c19c64d1ef30115d65a8641709f06e1a484`.

Starting commit: `169fadc75d87ece677ec60092b0eaf29abfa4a32`.

Target branch: `phase-1/sira-pilot-autonomous`.

Authorization identity:
`AUTH-T09-AUTONOMOUS-PREFLIGHT-TO-PILOT-2026-08-27`.

## Workstream and scope

This workstream repairs the pre-empirical provider/host authority and early-cleanup
control plane, qualifies one exact runtime end to end, freezes one V8 scientific
package, and then executes the already-approved four-cell calibration pilot. The
scientific contract is unchanged: EXP-0001; SiRA commit `93fb8d72...`; dated model
`gpt-4o-2024-11-20`; pinned FanOutQA snapshot/tasks/evaluator; A-reactive,
A-simulative, checkpoint, B-simulative, B-reactive; one attempt per cell; zero
condition retry; descriptive calibration only.

In scope are focused infrastructure repairs, up to eight sequential preflight
Lambda launches, one final empirical Lambda launch, exact-image qualification,
evidence retention, uniform downstream finalization, cleanup, and terminal
reconciliation. Out of scope are scientific changes, task or evaluator replacement,
condition retries, a larger pilot, training, comparative scientific conclusions,
and production-readiness claims.

## Definition of done

| ID | Contract | Required evidence | Status |
| --- | --- | --- | --- |
| AP-01 | Preserve Retry 5 and identify each slot's first causal failure from retained source-bound evidence. | Unchanged Retry 5 paths/hashes and source-grounded failure projection. | met |
| AP-02 | Give normalized authority-tree and nested eligibility-source manifests distinct typed identities across provider and host. | Focused pass/fail binding tests on the exact retained Slot 2 tree. | met |
| AP-03 | Initialize durable cleanup state immediately after one exact provider instance ID is returned and before staging or remote mutation. | Ordering test and private state receipt with exact owner, resource/secret locations, and empirical-entry bit. | met |
| AP-04 | Make basic host cleanup and provider termination independent of pilot, attempt, artifact, or image state. | Early-abort cleanup regression with no `pilot-state.json`, terminal provider receipt, and safe cleanup summary. | met |
| AP-05 | Preserve process-wide core suppression and prohibit core retention. | Exact Docker `--ulimit core=0:0`, entrypoint assertion, inheritance, abort, Chromium, and zero-core receipts. | met-local; exact-image receipts pending AP-09 |
| AP-06 | Apply equal 536,870,912-byte per-attempt, 2,147,483,648-byte aggregate, and 67,108,864-byte essential-failure evidence caps. | Constants/contracts, equality/overflow tests, exclusions, and cap arithmetic. | met |
| AP-07 | Pass focused local repair tests, `make validate`, diff hygiene, and one independent spec-conformance review before live mutation. | Commands, outputs, reviewer verdict, rereview if needed, and clean repair commit. | partial-review-and-clean-commit-pending |
| AP-08 | Bind every preflight launch to current-turn authorization, fresh identity, one simultaneous A10, no persistent filesystem, 6-hour individual/12-hour cumulative active limits, and USD 20 preflight cap. | Private authorization/volume records, cloud ledger, provider receipts, and accounting. | not-started |
| AP-09 | Pass all 16 preflight qualification checks in the exact accepted image and final container path. | Machine-readable qualification receipts with zero task requests/actions. | not-started |
| AP-10 | Freeze a clean V8 commit, one unchanged image, exact dependencies/model/tasks/evaluator/browser/configuration, four commands, two valid pair diffs, fresh identities, and one run manifest. | Commit/image/manifest hashes and clean-tree receipt. | not-started |
| AP-11 | Execute Task A reactive and simulative once each with reconstructable raw evidence and uniform finalization. | Entry/raw-complete/usage/cleanup/evaluator/score receipts; zero retry. | not-started |
| AP-12 | Apply the predeclared first-pair continuation checkpoint without result selection. | Append-only checkpoint binding pair validity, safety, budgets, informativeness, and time. | not-started |
| AP-13 | If the checkpoint passes, execute Task B simulative and reactive once each with the same runtime/finalizer/evaluator. | Equivalent per-attempt and pair-matching evidence; zero retry. | not-started |
| AP-14 | Enforce calls, tokens, actions, attempts, empirical wall, cleanup reserve, OpenAI/Lambda/new/cumulative spend, and raw-storage limits. | Runtime budget ledgers and actual accounting. | not-started |
| AP-15 | Retain verified safe evidence, remove containers/browser/core/secrets, terminate the exact instance, restore provider security, and prove zero T09 instances. | External manifests/hashes, provider closeout, and cloud-ledger terminal events. | not-started |
| AP-16 | After provider termination, run full repository gates, independent evidence review, and publish a non-comparative 15-item handoff. | Full checks, review verdict, disposition/control records, and final report. | not-started |

## Implementation mapping and planned evidence

- AP-02–AP-04 map to `src/giclab/harness/t09_pragmatic_provider.py`,
  `containers/sira-smoke/pragmatic/t09_remote_runner.py`, and focused T09 tests.
- AP-05–AP-06 map to the remote runner, execution/runtime contracts, generated
  command manifests, condition plans, and cap/core regressions.
- AP-07–AP-10 map to focused tests, repository validation, clean commits, exact live
  qualification receipts, generated V8 contracts, and the frozen run manifest.
- AP-11–AP-15 map to immutable raw-attempt trees, raw/essential seals, usage/budget
  ledgers, uniform evaluator/finalizer receipts, provider journals, and verified
  external evidence.
- AP-16 maps to the completed plan ledger, terminal disposition/control surfaces,
  full `make check`, independent evidence review, and final response.

## Progress and decisions

- `2026-08-27`: verified the required clean starting commit and created the requested
  branch. No new cloud/model/browser action had occurred.
- `2026-08-27`: retained Retry 5 proves Slot 1 first failed on historical/current
  finalizer-hash conflation; the retained lineage already repaired that primitive.
  Slot 2 first failed because the provider bound nested pre-empirical source manifest
  `13033996...` while the host projected outer normalized-tree manifest `a3709fc6...`
  under the same field. Cleanup independently failed before `pilot-state.json`
  existed. All Retry 5 cells remain not run.
- Decision: preflight engineering uses one stable autonomous authority and fresh
  engineering-attempt identities; V8 scientific identities are minted only after
  exact end-to-end qualification.
- Decision: cleanup authority is a first-class private provider/host state surface,
  not a derivative of later pilot state.
- `2026-08-27`: typed authority, early cleanup, output-cap, authorization, fresh-ID,
  and command-normalization regressions pass (`111` focused T09 tests). `make
  validate`, strict type checking, lint, and diff hygiene pass. The four V8 command
  manifests machine-diff valid for both task pairs, with only treatment, order,
  identity, condition-plan, and output-root differences.
- Decision: preserve the V7 condition plans as versioned proposal inputs while the
  active condition-plan directory contains only the four fresh V8 children. The
  prior Retry 5 terminal control remains immutable evidence but no longer governs
  the current-turn V8 authorization.
- `2026-08-27`: the first independent V8 conformance review found four blockers:
  package authorization was rejected by the runtime verifier, provider authority
  still encoded Retry 5's two-launch lifecycle, the exact raw/essential sealers
  were not exercised in live preflight, and argv normalization orphaned an output
  flag. Commit `a5b38abe5984d478d3317e04fbbcbdb27a36f34f` repairs all four
  primitives. The focused suites now pass 115 tests, including exact production
  raw/essential reconstruction, same-host preflight repair, complete flag/value
  projection, and 8/9 launch-boundary regressions; validation, strict typing, lint,
  and diff hygiene pass. Independent rereview and the final clean-package verifier
  remain required before live mutation.

## Budgets, blockers, and next phase

Prior cumulative T09 spending is USD 6.8131387350. New ceilings are USD 20
preflight Lambda, USD 8 empirical Lambda, USD 40 OpenAI, USD 68 aggregate, and USD
75 cumulative T09; 8 preflight launches, 1 empirical launch, 12 cumulative
preflight active hours, 6 hours per preflight instance, 4,620 calls, 4,000,000
tokens, 120 browser actions, 4 empirical attempts, zero retries, one simultaneous
instance, and zero persistent filesystems.

The material blockers are exactly the ten conditions named by the source contract.
Repairable preflight defects are not blockers. The next permitted phase is exact
live preflight after AP-02 through AP-08 are met. Scientific freeze is permitted
only after AP-09 is met, and empirical execution only after AP-10 is met.

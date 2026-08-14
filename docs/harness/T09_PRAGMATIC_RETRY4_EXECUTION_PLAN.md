# T09 Pragmatic Retry 4 Execution Plan

Status: **complete at `t09-pilot-blocked-material-risk`; V6 authority exhausted**

Source contract: the 2026-08-14 Retry 4 user instruction at SHA-256
`e3222d38c9b21091a51839122d42594d691577716bc87fd3e09296c6b766df51`.

Starting commit: `bf224a323f8f3fd067a4a54d2f0e83a6a6fec0b2`.

Target branch: `phase-1/sira-pilot-pragmatic-r4`.

Target plan: `PLAN-EXP0001-PILOT-V6`.

## Scope

Retry 4 makes exactly two infrastructure repairs: safe content-addressed staging of
the retained V4 regression archive, and separation of cumulative active-provider,
per-launch preflight, and post-freeze empirical clocks. It then qualifies one exact
image and executes the unchanged two-task, four-attempt calibration pilot when every
pre-entry gate passes.

The scientific locks remain the two pinned FanOutQA tasks, SiRA commit
`93fb8d72de71f9a4a13419670adeb34d93cf7acd`, model
`gpt-4o-2024-11-20`, the pinned evaluator, counterbalanced order, one attempt per
task-condition, zero condition retry, and descriptive-calibration interpretation.

Out of scope are a new execution platform, image-reproducibility project, evaluator
redesign, scientific task/model/configuration changes, training, a larger pilot, and
comparative scientific conclusions.

## Definition of done

| ID | Contract | Required evidence | Status |
| --- | --- | --- | --- |
| R4-01 | Preserve all Retry 3 plans, identities, dispositions, provider journals, image records, and external evidence as zero-empirical historical records. | Immutable-path/hash regressions and no reused V5 identity. | met: V5 plan/runtime/execution/command bytes are archived at their exact historical hashes; disposition and terminal control remain byte-exact |
| R4-02 | Stage the private regression archive by verified size/content into one exclusive canonical target without following links or mutating the source. | Focused pass/fail tests for alternate source path, bad bytes/size, symlink, special file, preexisting target, target rehash drift, source immutability, fsync, and cleanup. | met: one descriptor-based no-follow/O_EXCL/fsync primitive and focused adversarial tests pass |
| R4-03 | Separate cumulative active Lambda accounting, a fresh 3,600-second clock for each provider preflight, and a 14,400-second empirical clock beginning only after durable frozen-manifest publication. | Typed state/contracts plus exact fake-clock boundary regressions. | met: three typed clocks, durable future-origin manifest publication, and exact Retry 3 failure/equality/overflow tests pass |
| R4-04 | Enforce at most two sequential launches, one simultaneous instance, 3,600-second failed-preflight limit, 300-second termination dispatch, 21,600 cumulative active seconds, USD 8 Lambda, USD 48 new, and USD 55 cumulative T09 spend. | Source-bound provider receipts, equality/overflow tests, and cloud ledger. | met: exactly two sequential hosts used 4,419.078072 active seconds / USD 1.583502976 Lambda; one exact termination request per host proved terminal/absent, zero instances, restored security, and no wall exception |
| R4-05 | Verify and prefer the retained 1,207,128,576-byte image archive at SHA-256 `623e717c…`; otherwise build exactly one replacement and qualify it. | Local archive verification and live image-load/build receipt. | met: slot 1 made the one permitted fallback build and retained image `sha256:abe8ed38…`; slot 2 imported that exact archive with import count one, additional build count zero, and passed full qualification |
| R4-06 | Issue fresh V6 plan, host, qualification, attempt, evaluator, pair, stage, archive, and provider-slot identities while preserving every scientific field. | Machine science projection equality, four command manifests, and two valid pair diffs. | met: plan `d0294b3a…`, repaired runtime `7bf16e30…`, execution `17de56ba…`, four V6 condition plans, four exact commands at `51db96ed…`, and both pair diffs are bound and valid |
| R4-07 | Freeze a clean static package and pass only focused staging/clock/provider/image/qualification/pair/budget/cleanup tests, `make validate`, diff hygiene, and focused spec-conformance review before launch. | Exact commit, commands, test output, reviewer verdict, and clean tree. | met: reviewed ancestor `c62f92a0…`, clean package `2b40b8a8…`, 23 focused tests, validation, Ruff, strict mypy, diff hygiene, exact package verification, and independent narrow PASS preceded empirical entry |
| R4-08 | Bind least-privilege credentials, approved attached-volume retention, hardware/runtime identity, budget authority, and cleanup policy before the first cloud mutation. | Private authorization/volume records and cloud-run ledger `planned`/`launch_intent` events without secret values. | met: package-bound private authorization/volume records and cloud ledger preceded slot 1; only single-key secret material reached the host and was removed before termination |
| R4-09 | Dynamically qualify the exact image, evaluator, real-evidence regression, browser lifecycle, model metadata, pair diffs, and frozen run manifest within one preflight wall. | Source-derived live receipts and frozen-manifest SHA-256; zero task requests/actions before entry. | met: slot 2 imported and qualified the exact retained image, passed every listed gate, made one metadata GET, and froze manifest `c633c835…` before a fresh empirical clock with zero prior task calls/actions |
| R4-10 | Execute A-reactive, A-simulative, B-simulative, and B-reactive once each, sealing/exporting/verifying raw evidence before later empirical entry. | Four empirical-entry records, raw seals, verified exports, usage receipts, cleanup receipts, and zero retry. | partial: A-reactive entered exactly once and retained 20 calls / 38,779 tokens / 5 requested actions, but an oversized core made the raw seal fail after the output-byte stop; zero retry and the raw-ack gate correctly prohibited all later conditions |
| R4-11 | Apply one uniform network-disabled finalizer and the predeclared first-pair continuation rule before Task B. | Selected finalization receipts, uniform closure proof, pair checkpoint, and matched-pair diffs. | blocked: the finalizer was qualified but could not run without an accepted immutable raw seal; no Task A pair or checkpoint exists |
| R4-12 | Prioritize cleanup, retain available evidence, terminate the exact instance, prove terminal/absent and restored security, remove secrets/containers/rulesets, and reconcile actual active time/cost. | Verified final archive and provider closeout receipts plus terminal cloud-ledger events. | met: cleanup/termination passed; the byte-exact original archive is supplemented by one independently reviewed 597,140-byte post-termination overlay at manifest `1eedf1d9…`, frozen-runtime reconstruction passes, and clock receipt `989d5625…` reconciles the preserved provider receipts without rewriting them |
| R4-13 | After termination, run broader repository/privacy/evidence gates, focused independent evidence review, and update registry/state/readiness/notebook/decision surfaces without overclaiming. | Full gate output, reviewer verdict, and converged public/machine state. | met: independent evidence rereview found no material residual; terminal disposition/control, registry, project state, readiness, notebook, and decision surfaces converge; portable-Quarto `make check` passes Ruff, strict mypy, all 1,414 tests, repository validation, 16-page rendering, and site validation |
| R4-14 | Report descriptive outcomes and operational feasibility only, including all 17 requested handoff items. | Final response and terminal ledger state; no EXP-0001 pass/fail or superiority claim. | met at final handoff: this ledger and the accompanying 17-item response preserve the infrastructure-invalid/unscored boundary and make no EXP-0001 or condition-comparison claim |

## Authorization and budgets

Current-turn authority covers the two repairs, focused local validation, a fresh V6
package, up to two pre-empirical Lambda launches, one four-attempt campaign, OpenAI
spend up to USD 40, Lambda spend up to USD 8, new spend up to USD 48, cumulative T09
spend up to USD 55, evidence collection, and provider termination. Condition retries,
task/evaluator/model changes, post-entry scientific-runtime changes, training, and a
larger pilot are not authorized.

Default cleanup is verified retention to the approved attached data volume followed
by exact provider termination. A failed preflight must begin termination within 300
seconds and may not retain the host for review or archive perfection.

## Progress log

- 2026-08-14: verified the clean Retry 3 closeout baseline and created branch
  `phase-1/sira-pilot-pragmatic-r4` at exact commit `bf224a323f…`.
- 2026-08-14: bound the source instruction at SHA-256 `e3222d38…`; no cloud,
  provider, model, browser, SiRA, or empirical action has occurred in Retry 4.
- 2026-08-14: implemented and focused-tested safe content-addressed regression-archive
  staging plus the three-clock lifecycle; **12 focused tests** pass with Ruff, strict
  mypy, bytecode compilation, and diff hygiene. The retained image archive rehashes to
  `623e717c…` at exactly 1,207,128,576 bytes on the writable approved volume.
- 2026-08-14: reran the network-disabled real-evidence regression on the exact V4
  archive, full dataset, pinned evaluator, and 51-package overlay; the accepted
  semantic projection remains `7bdf21f2…` with zero added model/browser activity.
- 2026-08-14: froze the V6 static plan/runtime/execution/condition/command hash
  cascade from reviewed implementation ancestor `4c9aa828…`; all four rendered
  commands and both matched-pair diffs validate, and `make validate` passes.
- 2026-08-14: focused review found and the implementation fixed one post-freeze
  admission receipt key mismatch before launch; the writer and reader now share one
  typed constant and a direct pass/fail receipt regression.
- 2026-08-14: slot 1 fully qualified fallback image `sha256:4ce9c92a…`, froze
  manifest `4477f531…`, and issued one metadata GET with zero task calls/actions.
  Task A reactive then stopped before empirical entry because the runtime compared
  the raw attempt directory against its parent logical output root. The attempt
  identity was not consumed; evidence stage `18f6c7d6…` was verified off host and
  provider closeout `5dd82529…` proved terminal/absent and restored security.
- 2026-08-14: implemented the focused pre-entry repair: runtime admission now binds
  `raw_output_root`, privileged Docker load addresses the live parent-held verified
  descriptor, and slot 2 requires source reconstruction of the exact slot-1 archive,
  provider entry/closeout, zero usage, and unchanged scientific projection.
- 2026-08-14: rebound the unchanged V6 plan from focused repair ancestor
  `009913ae…`; runtime `0fbfb31a…`, execution `2496d9bb…`, command package
  `6b75b071…`, four manifests, and both pair diffs close without scientific drift.
- 2026-08-14: focused rereview found that slot 2 could still fall back to a second
  build after an import failure. The root control is now typed from the source-bound
  launch slot: slot 1 permits the one campaign fallback, slot 2 is import-only, and
  both missing and rejected-load regressions prove zero build calls. The rebound
  ancestor is `c6197509…`; runtime `0b0f0c09…`, execution `a53a482d…`, and command
  package `2ea7b11b…` preserve the four commands and two valid pair diffs.
- 2026-08-14: after the single authorized slot-2 provider POST, a read-only preflight
  inspection found that the host did not retain the exact source-manifest-bound slot-2
  authority and used a stale transition-mode label in raw export. Before any host,
  model, browser, SiRA, or empirical action, the focused descendant `afea34c1…` bound
  the active provider-entry package transition, minimal authority projection, frozen
  manifest, raw-export closure, and provider closeout lineage without scientific drift.
- 2026-08-14: two host-control invocations stopped before importing the runner because
  the OS Python was 3.10 and its system `jsonschema` was stale; both logs contained zero
  secret matches and no gate or provider request ran. A pinned Python 3.11.14 control
  runtime was materialized, and the entry freshness gate was aligned from the obsolete
  1,800-second value to the authoritative 3,600-second per-launch preflight wall.
- 2026-08-14: clean package `2b40b8a8…` received independent prelaunch PASS. Slot 2
  then imported image `sha256:abe8ed38…` without a build, passed the real-evidence,
  evaluator, browser, package, pair, credential, and one-metadata-GET gates, and froze
  run manifest `c633c835…` before the fresh empirical clock.
- 2026-08-14: Task A reactive crossed empirical entry once. After 20 calls, 38,779
  tokens, five requested actions, and four retained post-action results, a 234,479,616-
  byte core file pushed the raw tree beyond the 67,108,864-byte hard cap. The host
  stopped the container with exit 143, then the raw seal failed closed with
  `raw attempt exceeds its hard byte cap`. No evaluator or score was produced and the
  no-retry/raw-ack boundary prohibited all later conditions.
- 2026-08-14: host cleanup removed the container, image, private regression staging,
  and temporary OpenAI secret. Aggregate private stage `8b647302…` was verified
  off host, one exact provider termination request produced terminal/absent, zero-
  instance, and restored-security evidence, and final archive manifest `4b7bc842…`
  was sealed. Retry4 cost is USD 1.5835029759 Lambda plus USD 0.1175275 OpenAI.
- 2026-08-14: post-termination review found the aggregate producer had excluded one
  manifest-owned nested archive and that the raw closeout's campaign-duration label
  referred to slot-2 owned time, not empirical time. Clean repair package
  `13cbf56e…` received independent PASS, then created exact sidecar overlay
  `ARCHIVE-EXP0001-PILOT-V6-0004-POSTRUN-OVERLAY-0001`. Its manifest is
  `1eedf1d9…`, identity is `a07cee4c…`, and clock reconciliation is `989d5625…`.
  The one added member is 597,140 bytes at `18f6c7d6…`; reconstructed frozen loading
  passes at `c633c835…`, while all four original archive hashes remain unchanged.
- 2026-08-14: independent postrun rereview of closure commit `a003a9b6…` found no
  material residual across the original archive, additive overlay, clock arithmetic,
  privacy boundary, terminal control, and public/machine state. Broad-gate alignment
  commit `462fb3f9…` then removed stale V5-as-current test assumptions. The final
  portable-Quarto 1.9.38 `make check` passes Ruff, strict mypy, all 1,414 tests,
  repository validation, all 16 notebook pages, and site validation.

## Next permitted phase

No V6 execution remains permitted. Preserve the byte-exact original archive together
with its post-termination sidecar overlay and this one consumed, infrastructure-invalid,
unscored attempt. Before requesting fresh authority, disable or strictly bound core-
dump creation and prove that an output-cap stop always produces a reconstructable
privacy-safe raw failure seal. A future calibration must mint fresh plan, host,
attempt, pair, stage, archive, and authorization identities; a larger pilot is not
justified by this record.

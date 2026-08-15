# T09 Pragmatic Retry 5 Execution Plan

Status: **in-progress**

Source contract: the 2026-08-14 current-turn user instruction, **T09 Pragmatic
Retry 5 — Disable Core Dumps, Repair Failure Sealing, and Complete the
Calibration Pilot**.

Starting commit: `3f4e4e346e0f5ef4633de55a801e702e34ed6e3b`.

Target branch: `phase-1/sira-pilot-pragmatic-r5`.

Target plan: `PLAN-EXP0001-PILOT-V7`.

Authorization identity: `AUTH-T09-PRAGMATIC-RETRY5-2026-08-14`.

## Scope and fixed contract

Retry 5 makes exactly two execution-infrastructure repairs: disable core dumps
for the complete condition/browser/finalizer process tree, and preserve a small,
privacy-safe, reconstructable essential failure bundle when the full attempt tree
breaches its evidence cap. It then reuses and functionally qualifies the retained
image, freezes fresh V7 identities and exact commands, and executes at most one
fresh zero-retry attempt for each of the four locked task-condition cells.

The scientific contract remains EXP-0001; SiRA commit
`93fb8d72de71f9a4a13419670adeb34d93cf7acd`; dated model
`gpt-4o-2024-11-20` for every role; FanOutQA November 2023 development snapshot
at commit `989f4c40d9deea1ecb0897d7a17a9c0fe20d5c33` and blob
`76ad1feb689b754bfe4e5e24d3ea371b647efa67`; Task A
`7dcbbbdc7f1120cd`; Task B `2120afba8009bad3`; the exact pinned evaluator;
counterbalanced order A-reactive, A-simulative, checkpoint, B-simulative,
B-reactive; one attempt per cell; zero condition retries; descriptive calibration
only.

Out of scope are a new execution platform, image-reproducibility or finalizer
redesign, task/evaluator/model/treatment changes, post-entry scientific-runtime
changes, training, a larger pilot, comparative claims, and an EXP-0001 outcome.

## Budget, storage, and cleanup contract

- New OpenAI cap: USD 40.00.
- New Lambda cap: USD 8.00.
- New campaign aggregate cap: USD 48.00.
- Cumulative T09 cap: USD 60.00 from a recorded prior USD 5.7424506112.
- Calls/tokens/browser actions: 4,620 / 4,000,000 / 120.
- Fresh condition attempts/retries: 4 / 0.
- Lambda launches/simultaneous instances/persistent filesystems: 2 / 1 / 0.
- Preflight/empirical/cleanup/cutoff/cumulative-active ceilings: 3,600 / 14,400 /
  900 / 13,500 / 21,600 seconds.
- Durable private retention: the source-bound attached data volume; verify the
  copy and hashes, then terminate. Cleanup takes priority over analysis, image
  export, finalization, repository tests, and documentation.

## Definition of done

| ID | Contract | Required evidence | Status |
| --- | --- | --- | --- |
| R5-01 | Preserve all Retry 4 plans, manifests, provider receipts, archives, disposition, terminal control, and consumed identities. | Immutable hashes and explicit V6 attempt states; no V6 identity in V7. | met: exact V6 plan/runtime/execution/command bytes are archived; disposition and external evidence remain unchanged; V7 uses fresh identities |
| R5-02 | Inspect only safe retained-core metadata and classify the producer when possible without disclosing memory content. | Private mode-0600 receipt with relative path, metadata, ELF class, safe producer family, and unavailable fields explicit. | met: private receipt `core-producer-metadata.json` is mode 0600, 697 bytes, SHA-256 `cdbe6918d94daa233ea76d6cb0bb07f23b8d00af4d7fab05051ab8ee5bf516d1`; bounded metadata identifies an x86-64 Chromium-family core and leaves the signal unavailable |
| R5-03 | Enforce RLIMIT_CORE `(0, 0)` for every condition/browser/finalizer descendant without privilege or host-wide changes. | Exact Docker argv, entrypoint assertion, child/grandchild receipt, fail-before-entry behavior. | partial: Docker/entrypoint/runtime/finalizer enforcement and focused regressions pass; exact-image receipt remains dynamic |
| R5-04 | Prove suppression in the exact final image/container path. | Synthetic SIGABRT nonzero exit with zero core, inherited zero limits, Chromium teardown with zero core/process residue. | partial: local inheritance/SIGABRT and browser-path regressions pass; exact accepted-image proof remains dynamic |
| R5-05 | Detect filename and ELF `ET_CORE` artifacts without misclassifying ordinary large files. | Bounded scanner fixtures and exact final-runtime use. | met: bounded filename/ELF fixtures, full inode-alias census, external-hardlink and symlink cases, and an 8 MiB ordinary-file negative regression pass |
| R5-06 | Treat any core as prohibited transient security material: stop, record safe metadata, exclude, destroy, and gate continuation. | Core incident/cleanup receipt, archive exclusion, no scientific-raw classification. | partial: source and focused state/archive/cleanup regressions now remove every owned alias, report verified versus unverifiable destruction truthfully, require rotation on unverifiable destruction, reject malformed cleanup evidence, and close slot-2 admission; live receipts remain dynamic |
| R5-07 | Seal a reconstructable essential failure bundle after an output-cap/infrastructure stop. | Allowlisted bundle, exclusion manifest, schemas, secret/privacy scans, source-grounded status, independent archive. | partial: both empirical and pre-empirical consumed-failure fixtures pass seal, export, independent verify, off-host restore, and reconstructable-disposition checks; neither is evaluator eligible and no V7 live attempt has exercised the path |
| R5-08 | Retain a finite, equal evidence cap justified by expected scientific evidence rather than core size. | Retry4 non-core arithmetic plus projected screenshot/log/receipt/evaluator envelope. | met: 2,076,704 observed non-core bytes; 50,331,648-byte conservative full-attempt projection; 16,777,216-byte headroom within the unchanged 67,108,864-byte cap |
| R5-09 | Reuse and qualify the retained 1,207,128,576-byte image archive at SHA-256 `623e717c…`; rebuild only if functionally necessary. | Source-bound archive verification, exact image ID, functional receipts, build/import count. | partial: the exact archive size/SHA and expected image ID were reverified locally and on launch slot 1; slot 1 stopped before image import, so exact slot-2 import and qualification remain dynamic |
| R5-10 | Preserve the repaired preflight, empirical, cleanup, termination, launch, and cumulative-active clock contract. | Typed contracts, boundary tests, source-bound live receipts. | partial: typed V7 limits and source checks are implemented; launch slot 1 closed pre-empirically after 1,431.636539 active seconds at USD 0.5130030931, attempt export uses the empirical campaign origin, and slot-2 cumulative headroom remains source-bound; empirical receipts remain dynamic |
| R5-11 | Mint fresh V7 plan, host, qualification, attempt, evaluator, pair, stage, archive, and provider identities. | Identity registry/tests and no prior reuse. | met: V7/0005 identities are registered and V6 reuse is rejected |
| R5-12 | Freeze a clean reviewed V7 package, one image, four commands/configs, two valid pair diffs, and one immutable run manifest before empirical entry. | Commit/hash closure, focused review PASS, dynamic qualification and freeze receipts. | partial: independently reviewed repair ancestor `df95199bfa897db78479828ae8d07f63b93afa09` received PASS and the static V7 runtime, condition, execution, command, and pair-diff bindings are regenerated; final package review and the dynamic accepted-image manifest remain pre-entry |
| R5-13 | Execute the four fresh attempts in the locked order with zero retry and raw-or-essential evidence export after every consumed attempt. | Per-attempt entry, terminal, usage, seal, export acknowledgement, cleanup, evaluator, and score evidence. | not-started |
| R5-14 | Apply the predeclared first-pair continuation rule before Task B. | Append-only checkpoint binding both Task A attempts, uniform finalizer, pair validity, safety, cost, and time headroom. | not-started |
| R5-15 | Keep credentials structurally outside evidence and destroy temporary material; any actual exposure stops continuation. | Exact-secret scans, structural privacy receipts, cleanup, no core transfer. | partial: structural/exact-value controls and canary regressions pass; live cleanup receipts remain dynamic |
| R5-16 | Enforce calls, tokens, actions, attempts, zero retries, OpenAI/Lambda/new/cumulative cost, wall, disk, and output limits at runtime. | Equality/overflow regressions plus live budget ledgers and provider accounting. | partial: runtime caps and static arithmetic are bound; stdout and stderr each use a declared 67,108,864-byte limit whose saturation is an explicit consumed infrastructure stop, and non-empirical cap consumption blocks replay before Docker; live ledgers/accounting remain dynamic |
| R5-17 | Verify durable evidence, then remove containers/browser/core/secrets, terminate the exact instance, prove terminal/absent and zero T09 instances, and restore firewall state. | Local-volume verification, provider closeout bundle, security restoration, cloud-run ledger. | partial: launch slot 1 evidence was copied and verified off-host, its isolated secret was destroyed, the exact instance was terminated, and provider closeout proves zero T09 instances; slot 2/campaign cleanup remains dynamic |
| R5-18 | Reconstruct results, run broader gates, obtain independent evidence review, and converge public/control surfaces without comparative inference. | Final disposition/control, repository ledger/docs/notebook, validation/test/lint/type/site results, 18-item handoff. | partial: prelaunch registry, decision, readiness, plan, ledger, experiment, and notebook surfaces identify V7; terminal evidence and final gates await execution |

## Assembly evidence log

- `2026-08-14`: clean branch forked from the exact required starting commit.
- `2026-08-14`: Retry4 disposition records one consumed infrastructure-invalid,
  unscored A-reactive attempt; other conditions were not run and no pair exists.
- `2026-08-14`: the private sealed archive identifies one 234,479,616-byte,
  mode-0600 x86-64 ELF core at the previously recorded attempt-relative location.
  A bounded `file(1)` classification identifies the Chromium process family;
  signal detail is unavailable without unsafe memory inspection. The value-safe
  private receipt is 697 bytes at SHA-256
  `cdbe6918d94daa233ea76d6cb0bb07f23b8d00af4d7fab05051ab8ee5bf516d1`.
- `2026-08-14`: focused V7 regressions pass for Docker/entrypoint core suppression,
  inherited child/grandchild zero limits, synthetic abort without core, browser
  teardown scanning, filename and ELF detection, large-file negative classification,
  core destruction/exclusion, permanent safety stop, essential failure sealing,
  privacy canaries, evidence-cap arithmetic, fresh identities, pair diffs, and zero
  retry.
- `2026-08-14`: adversarial follow-up regressions cover hardlinked and symlinked
  core identities, in-root aliases of a core inode, unverifiable destruction and
  malformed cleanup receipts, explicit stdout/stderr saturation, empirical-clock
  export cutoff, exact metadata/freeze absence for slot-2 eligibility, and both
  empirical and non-empirical essential-seal export/verify/restore paths.
- `2026-08-15`: immutable source commit
  `3e1b33f47ab956dd009dd377cbda6e8350fba9d6` received independent PASS after
  moving the full recovery core/security census ahead of every partial or complete
  raw-authority read. Named, ELF `ET_CORE`, and external-hardlink fixtures cover
  both raw-prefix states; clean manifest-only recovery remains resumable.
- `2026-08-15`: static V7 bindings were regenerated in dependency order from the
  reviewed source ancestor: runtime identity, four condition plans, execution
  contract, generated command manifests and pair diffs, terminal successor, and
  registry/project-state authority. Repository validation and 172 focused
  Retry5/pilot/protocol/control tests pass before the clean package commit.
- `2026-08-15`: launch slot 1 crossed no empirical, model-task, browser, image-import,
  or image-build boundary. A preflight-only historical/current finalizer hash
  conflation stopped before image materialization. The isolated secret was
  destroyed, all safe source evidence was copied off-host, the exact instance was
  terminated, and provider closeout proves zero T09 instances. Active duration was
  1,431.636539 seconds and Lambda list cost was USD 0.5130030931.
- `2026-08-15`: focused repair ancestor
  `df95199bfa897db78479828ae8d07f63b93afa09` received independent PASS. V4
  historical evidence now binds its original finalizer explicitly while the V7
  finalizer remains independently qualified; closed slot-1 evidence normalizes
  under collision-free `slot1-*` paths, and the exact `02524c7` to repaired-package
  transition is ancestry/allowlist/runtime bound with unchanged science.

## Next permitted phase

Complete the repaired static V7 package closure and focused independent package
review. The second and final cloud launch remains prohibited until that review,
the external volume, private cloud ledger, source-bound slot-1 closeout, and all
dynamic pre-entry qualification inputs are ready. After launch, cleanup and exact
provider termination take priority over analysis or documentation.

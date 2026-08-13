# T09 pragmatic Retry 2 execution plan

Assembly status: **in-progress**

## Source contract

This plan implements the user-supplied Retry 2 contract
(SHA-256 `3852fe8dabb9ee6b10e40cbc6dc1ab964ea6fce11f71f81f0966e927cadddeb9`)
from clean starting commit `5dd1b4f1d026b821d6cdbc86f07f43c3732e3888` on
`phase-1/sira-pilot-pragmatic-r2`.

The current-turn contract authorizes one new Lambda campaign, one launch, the exact
model-availability request, and—only after the replacement runtime passes its
functional-equivalence gate—the locked two-task/four-attempt calibration pilot. It
caps new OpenAI spend at USD 40.00, new Lambda spend at USD 5.16, new aggregate spend
at USD 45.16, and cumulative T09 spend (including USD 0.414064252316667 already
incurred) at USD 46.00.

## Scope

In scope: preserve V3 evidence; replace cross-run image-ID equality with one typed
replacement-image qualification and pre-entry binding; freeze V4/0002 identities;
run focused gates and independent review; execute at most four zero-retry attempts in
the locked order; retain, transfer, evaluate, reconcile, terminate, and report.

Out of scope: changing either task, dataset, evaluator, model, SiRA revision,
treatment, ordering, scoring, interpretation, or scientific budget; creating a new
cloud platform, watchdog, reproducibility project, training run, or confirmatory
claim; public release of private task or trace evidence.

## Definition of done

| ID | Requirement | Implementation / evidence | Status |
|---|---|---|---|
| R2-01 | Preserve the V3 disposition, archive, provider receipts, image observation, and all V3/T07 identities byte-for-byte. | Disposition remains `cb6ba0…`; V3 plan/condition bytes are archived; the typed V4 supersession records zero prior empirical use. | met |
| R2-02 | Freeze exactly the existing science: EXP-0001, two task IDs/hashes, FanOutQA revision, SiRA commit, GPT-4o snapshot, evaluator, counterbalance, zero retry, calibration-only interpretation. | Dataset/evaluator hashes, V3/V4 science-lock regression, execution schema, and four fresh 0002 attempts. | met |
| R2-03 | Build the candidate only from pinned inputs and retain base, Containerfile, complete context, source, dependency, browser, evaluator, entrypoint, environment, build-command, Docker/BuildKit, and SOURCE_DATE_EPOCH evidence. | Reviewed builder emits a complete safe context manifest and source/tool/build receipts; live candidate evidence is pending. | met-statically; dynamic-pending |
| R2-04 | Replace historical image-ID equality with a typed acceptance rule: one accepted replacement image, exact ID bound before empirical entry, and unchanged image verified for every attempt. | Typed qualification plus mode-0600 O_EXCL frozen manifest; every consumer rejects tags/static substitution. | met-statically; dynamic-pending |
| R2-05 | Compare available T07 image evidence and classify each observed difference without treating digest inequality alone as functional. | Historical inspect/setup hashes are pinned; comparator permits only verified functional equality, approved nonfunctional drift, or `historical_evidence_unavailable`. | met-statically; dynamic-pending |
| R2-06 | Pass final-container functional equivalence for Python 3.11.14, SiRA/source, workdir/entrypoint, packages/imports/evidence/budgets/tasks, exact offline evaluator fixtures, local browser lifecycle, command/pair diffs, cleanup, and exactly one model metadata request with no task request/action. | Corrected package/Chromium/patched-runner identities and exact fixture expectations are enforced; final-container gate awaits the host. | partial: static controls met |
| R2-07 | Freeze V4 plan, host/condition/evaluator/archive IDs ending in 0002, four commands/configs, code, runtime binding, and manifest before the first condition empirical event. | Plan `1ebfbb…` (6,465 bytes), execution `4cf469…`, commands `f8c008…`, reviewed source ancestor `dae76df…`; runtime manifest pending. | partial: static freeze met |
| R2-08 | Preserve a verified loadable image archive when it does not threaten the campaign/cleanup wall; otherwise record the exact limitation. | Bounded best-effort export path is implemented and cannot borrow cleanup reserve. | dynamic-pending |
| R2-09 | Enforce one 14,400-second provider clock, 13,500-second termination cutoff, 900-second cleanup reserve, next-attempt-only admission, one instance/launch, and zero persistent filesystem. | Shared typed lifecycle, provider-entry/closeout receipts, and exact fake-clock boundaries pass locally. | met-statically; provider evidence pending |
| R2-10 | Enforce fresh and cumulative cost limits, 4,620 calls, 4,000,000 tokens, 120 browser actions, four attempts, and zero scientific retry before each billable action. | Runtime counters and private-ledger schema enforce USD 40/5.16/45.16, prior USD 0.414064252316667 and cumulative USD 46, plus scientific caps. | met-statically; dynamic ledger pending |
| R2-11 | Run Task A reactive then simulative exactly once, evaluate both, and make the predeclared first-pair continuation decision. | Attempt archives/outcomes and checkpoint receipt. | not-started |
| R2-12 | When the checkpoint passes, run Task B simulative then reactive exactly once and evaluate both; otherwise stop without selection claims. | Attempt archives/outcomes or typed checkpoint stop. | not-started |
| R2-13 | Retain reconstructable, structurally redacted private evidence for every entered attempt and the maximal safe failure prefix. | V4 evidence/score schemas, direct-export verification and acknowledged-manifest regression pass; live archives pending. | partial: interfaces met |
| R2-14 | Prioritize cleanup: owned containers/browsers absent, temporary secrets destroyed, evidence copied as available, exact instance terminated/absent, firewall restored, regional rulesets absent, no T09 instance running. | Cleanup remains reachable from every prefix; provider closeout and export-deferral regressions pass; live receipts pending. | partial: controls met |
| R2-15 | Pass focused image/science/pair/timing/budget/evidence/cleanup tests, `make validate`, privacy scan, `git diff --check`, and independent spec-conformance review before launch; repair and rereview any material finding. | Focused 60-test suite, validation, Ruff, strict mypy, and diff hygiene pass; final package review is pending. | partial: review pending |
| R2-16 | After termination, reconcile actual Lambda/OpenAI usage, update public control surfaces without scientific overclaim, run proportionate broader gates/review, commit cleanly, and return all sixteen requested handoff items. | Compute/public records, final validation, clean commit, final response. | not-started |

## Control-plane decisions

- The tracked V4 plan freezes the scientific contract and the deterministic
  replacement-image selection procedure before launch. Because no local Linux Docker
  runtime exists, the exact image ID is necessarily observed on the one authorized
  host. A mode-0600, source-bound runtime binding becomes the authoritative image
  identity only after every equivalence check passes and before any condition entry.
  Every condition verifies that binding and the currently loaded image ID. This is a
  dynamic resource identity overlay, analogous to the already reviewed exact Lambda
  instance binding; it cannot change science or widen limits.
- The single-use provider authority and tracked V4 plan remain immutable for the
  campaign. Pre-entry infrastructure repairs may create a fresh qualification-attempt
  identity, but never another host launch or a scientific retry.
- Cleanup is permitted and required from every post-launch prefix, independent of
  qualification or attempt completeness.

## Planned evidence and commands

- Focused: `uv run --no-sync pytest -q tests/test_t09_sira_pilot.py`
- Static: `make validate`, repository privacy scans, and `git diff --check`
- Review: independent source/spec review, repair loop, and post-review focused smoke
- Dynamic: source-bound provider entry, image build/equivalence/runtime binding, exact
  command diff, model metadata, attempt exports, checkpoint, cleanup, closeout, and
  compute-use evidence
- Post-run: focused/full proportionate gates, independent evidence review, and public
  state reconciliation

## Progress and decision log

- 2026-08-13: verified the fresh R2 branch is clean at the required starting commit;
  local host is arm64 and has no Docker/Podman/Colima/OrbStack runtime, so the exact
  Linux/amd64 replacement image cannot be observed before the authorized host exists.
- 2026-08-13: audited V3 and confirmed the root defect is cross-run image-ID equality;
  pairing, task order, zero retry, budget enforcement, evidence export, and provider
  cleanup are reusable. Also identified a false V3 model-metadata claim that Retry 2
  must replace with the one explicitly authorized request.
- 2026-08-13: froze the selected V4 runtime source at reviewed-ancestor candidate
  `dae76df5915aeaa67b87dd13fc43557856e7fdce`, rebound the plan/runtime/execution/four
  condition/command contracts, and passed local focused, repository, lint, type, and
  diff gates. The final package binding and independent prelaunch verdict remain.

## Next permitted phase

Implement and locally validate the mapped V4 control-plane changes. No provider or
model request is permitted until R2-01 through R2-10 and R2-15 pass statically, the
single-use private authority/ledger is materialized, and the clean source package is
independently approved.

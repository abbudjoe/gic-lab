# T09 V10 provider accounting and closeout implementation ledger

Assembly status: **PR #3 remediation implemented and locally parity-verified; final
task-branch push and exact-head GitHub Actions verification remain**

Started: 2026-08-27

## Source and target contracts

The current user task is the authoritative Category 1 implementation contract. It is
constrained by `AGENTS.md`, `docs/PLANS.md`, the active Phase 1 plan, and the frozen
EXP-0001 scientific contracts. The target is a reviewable V10 successor package with
the existing reservation repair protected, one canonical offline-refinalization
receipt, and durable early cleanup authority. No live provider, model, browser, SiRA,
FanOutQA, evaluator, pilot, or cloud action is authorized.

Required base is `phase-1/sira-pilot-autonomous-r2` at
`503def0519e36f04b62b16158c72e11213b3bf9f`; starting tree is
`e033d28cee5478367cbdfc821e6b81c237ce8e44`. The accounting-repair ancestor is
`bb56edc68367e85b3a918f4b086c65cd578a231c`.

## Scope

In scope: provider-accounting regression protection; a deterministic, schema-bound
network-disabled refinalization receipt; versioned early cleanup state and fake-only
cleanup tests; an executable-but-unauthorized V10 plan; concise provenance and
preauthorization records; local validation; review; one commit, push, and draft PR.

Out of scope: V9 evidence mutation or reinterpretation; scientific changes; a new
infrastructure framework; credentials; provider/model requests; cloud mutation; live
Docker, browser, SiRA, FanOutQA, evaluator, or pilot execution; merge or auto-merge.

## Definition of done

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| V10-DOD-01 | Exact repository/base/ancestor/cleanliness checks and untouched full-suite baseline are recorded. | Git identities and baseline `make test`. | met |
| V10-DOD-02 | Outstanding provider reservations remain derived from owned per-call records with `math.fsum`, exact-empty semantics, atomic admission, one terminal per send, zero retries, and explicit lower/upper bounds. | Focused provider lifecycle, V8 33/30/3, V9 12-call three-pass, concurrency, flush, and shutdown tests. | met |
| V10-DOD-03 | `finalization-complete.json` is the one deterministic canonical offline-refinalization receipt and binds every required raw, science, source, runtime, evaluator, replay, mutation, semantic-output, and terminal identity under a JSON schema. | Schema tests, deterministic replay, identity-drift negatives, raw-manifest mismatch, privacy canary, and selector revalidation. | met |
| V10-DOD-04 | Exact provider ownership and later cleanup targets are retained in one durable versioned journal before package/source/image/secret/container/browser/campaign work; cleanup and a basic receipt do not require pilot state. | Failure-stage, missing-state, already-absent, repeated-cleanup, partial-persistence, exact-target, production fake-transport, and secret-canary tests. | met |
| V10-DOD-05 | Fresh `PLAN-EXP0001-PILOT-V10` and `AUTONOMOUS-0003` identities bind the repaired controls while all execution and compute permissions remain false. | V10 plan/schema validation, exact bytes/SHA-256, typed command render, science-hash regression, and command/config pair diff. | met |
| V10-DOD-06 | V8/V9 remain immutable historical evidence and every scientific field, timing bound, evidence cap, zero-retry rule, credential boundary, and interpretation limit is unchanged. | Historical hashes plus plan/contract regression tests and concise records. | met |
| V10-DOD-07 | Focused smoke, spec-conformance review, post-review smoke, formatting, Ruff, strict mypy, validation, privacy, full suite, diff check, and portable site gate satisfy the baseline policy. | Exact commands and results in this ledger. | met |
| V10-DOD-08 | Scope-reviewed changes are committed and pushed only to the task branch, and one draft PR is opened against the exact required base without auto-merge. | Final commit/tree, remote head/base, PR number/URL/state. | met — task branch pushed without force; draft PR #3 is open against the exact required base; auto-merge is disabled |

## Implementation mapping

| Work item | Mapped DoD | Target contract |
|---|---|---|
| Owned reservation projection and regressions | V10-DOD-02, V10-DOD-06 | The per-call reservation map is authoritative; aggregate projections are recomputed and an empty map is exactly zero. |
| Canonical completion receipt and schema | V10-DOD-03, V10-DOD-06 | Receipt creation follows immutable raw validation, is network/model/browser inert, contains no private payload, and deterministically identifies its full closure. |
| Early cleanup journal and closeout receipt | V10-DOD-04, V10-DOD-06 | Exact owned cleanup authority survives every pre-campaign failure and every update is a hash-chained immutable version. |
| Unauthorized V10 packet | V10-DOD-05, V10-DOD-06 | Fresh identities and unchanged science are executable by design but unavailable to any execution path until a later separately authorized Category 3 turn. |
| Review, gates, and PR | V10-DOD-07, V10-DOD-08 | No new regression, type, validation, privacy, or site failure; draft PR only. |

## Baseline evidence

- `git rev-parse phase-1/sira-pilot-autonomous-r2` ->
  `503def0519e36f04b62b16158c72e11213b3bf9f`.
- `git merge-base --is-ancestor bb56edc68367e85b3a918f4b086c65cd578a231c 503def0519e36f04b62b16158c72e11213b3bf9f` -> success.
- Starting worktree: clean; task branch created from the exact base.
- Untouched `make test`: **1474 passed, 39 failed in 48.39s**.
- Baseline failures are the exact historical-version/control-plane set in
  `test_exp0001_protocol.py` (6), `test_lambda_ssh_key_fingerprint.py` (1),
  `test_phase1_closeout.py` (2), `test_t08_sira_smoke.py` (1),
  `test_t09_retry3.py` (7), `test_t09_retry4.py` (4), `test_t09_retry5.py` (6), and
  `test_t09_sira_pilot.py` (12). The final run must add none.

## Progress and decisions

- 2026-08-27: Starting verification and baseline capture passed before edits.
- 2026-08-27: Confirmed the base retains the `bb56edc...` repair unchanged. It
  rebuilds reservation projections from the owned per-call map with `math.fsum` and
  has no subtractive reservation bookkeeping.
- 2026-08-27: Chose to evolve the existing finalization completion receipt rather
  than introduce a second competing downstream receipt.
- 2026-08-27: Chose one small hash-chained cleanup journal with injected exact-target
  actions; no general cloud orchestration layer will be added.
- 2026-08-27: The first independent conformance review failed because the initial V10
  packet still selected V9 execution assets and cleanup was only a tested primitive.
  The repair now has a separate typed, statically unauthorized V10 execution plane;
  the provider initializes cleanup inside its exact-owner protective block; the remote
  runner receives the hash-bound journal and registers exact secrets and containers;
  global cleanup can close from that journal without pilot state.
- 2026-08-27: Historical V9 remains on its frozen validation path. The V10 successor
  has its own schema, typed loader, deterministic command rerender, and pair-diff gate,
  preventing successor constants from retroactively reinterpreting V9.
- 2026-08-27: Rereview found that short-lived utility and finalizer Docker IDs were
  not entering the optional-state-independent journal. The common owned-Docker path
  now polls the daemon cidfile while the process is live, durably registers the exact
  ID, records verified normal removal, and preserves truthful removal evidence even
  when journal registration fails. Interruption and registration-failure regressions
  close through the journal with no pilot state.
- 2026-08-27: A same-path replay of the exact base identified one new V8 sealing
  fixture failure that aggregate counts had hidden. The primitive now takes explicit
  scientific-source and synthetic-lifecycle identity sets, preserving the historical
  V8 manifest while retaining strict V10 production ordering.

## Evidence log

- Final focused matrix: **61 passed** — 51 accounting, canonical receipt, early
  cleanup, and V10 plan cases plus 10 production/no-pilot/provider/V8 integration
  cases.
- The V9 release-order test executes the exact 12-call order three consecutive times
  and asserts an exactly empty positive-zero condition and aggregate projection.
- Production fake transports prove exact provider termination and security restoration
  when early-journal initialization fails, a single cross-host journal continuation,
  exact utility-container registration before process completion, and no-pilot cleanup.
- Independent spec-conformance review: passed after each material finding was repaired
  and rereviewed. Post-review focused smoke: passed.
- `make format`: passed. Ruff: passed. Strict mypy: passed. `make validate`: passed.
  Privacy/secret canaries and `git diff --check`: passed.
- Portable Quarto 1.9.38 `make site`: passed, including final site validation.
- Final `make test`: **1508 passed, 37 failed in 36.14s** versus the untouched start
  **1474 passed, 39 failed in 48.39s**. All 37 residual failures are members of the
  exact starting historical set; there are zero additions. Two historical fixtures
  were necessarily repaired in scope and now pass:
  `test_execution_schema_and_all_static_file_bindings_resolve` (typed unauthorized V10
  package closure) and
  `test_pragmatic_provider_entry_and_closeout_receipts_are_exact_and_source_bound`
  (durable cross-host cleanup continuation and closeout).
- Current V10 plan: 13,083 bytes; SHA-256
  `c6f36ffb0e719c2152c00fdd3f92cb18aa10a89e4a4a2e0f1179b167d6cfb68a`.
- The implementation commit `873196050eaf2138529929e1dc823cfdebcdc4e9`
  (tree `c30a7d9a6de9b3b299a87bf0ed3b2371b4e5ac0e`) was pushed without force to
  `origin/codex/t09-v10-accounting-closeout-repair`.
- Under explicit user authorization in a later turn, the missing remote base ref was
  published exactly at `503def0519e36f04b62b16158c72e11213b3bf9f` without force.
- Draft PR #3, `https://github.com/abbudjoe/gic-lab/pull/3`, was opened against that
  exact base. It is draft, open, mergeable, and has no auto-merge request. This
  ledger-only success update advances the final task head; the exact final commit and
  tree are reported after final push verification.

## Closeout and next permitted phase

No Category 1 blocker remains. Draft PR #3 now requires exact-head review by ChatGPT,
user approval of the reviewed SHA, and a separate Category 2 merge-only turn. No
Category 3 action is permitted; V10 remains unauthorized and unexecuted until fresh
Category 3 Luna authorization binds the exact merged commit and plan SHA-256.

## PR #3 exact-head remediation

Reviewed head `091fa6e690beeb628af54cec1e0a2849dd189e3b` (tree
`6e9dc95faf38bac7631fb42e3d73e74b17bb20e2`) received `CHANGES REQUIRED` after
GitHub Actions run `33164854474`. The Actions log is authoritative: its shallow
Linux checkout under Python 3.11.16 collected 1,545 tests and finished with **1,461
passed, 77 failed, 7 skipped**. The earlier 1,508/37 result came from an artifact-rich
developer worktree and is not a reproducible exact-head CI result.

The reproducible comparison uses one Python 3.11.14 interpreter and dependency
closure, full Git history, artifact-free detached worktrees, and symmetric deselection
of five explicitly private-local tests. Under that contract the exact base collected
1,508 tests and finished with **1,452 passed, 56 failed**. The reviewed head collected
1,540 tests and finished with **1,487 passed, 53 failed**. All 53 reviewed-head
failures were already failures on the exact base; three base failures had become
passing. The version-binding defect was therefore a real PR-introduced specification
regression hidden by a missing test surface, not a new failure in the old test set.
The remediation adds that missing surface and fixes the contract directly.

| ID | Required remediation outcome | Planned evidence | Status |
|---|---|---|---|
| V10-R-DOD-01 | Provider entry, qualification, rendering, and exact-owner cleanup use an explicit immutable version contract; no module-global latest-version fallback exists. | Frozen V3/V4/V5/V6/V7/V8/V9/V10 contracts plus positive and cross-version negative tests. | met |
| V10-R-DOD-02 | Every PR-introduced defect and every CI-only environment/private-fixture defect is classified and repaired without weakening historical authority, cleanup, privacy, or scientific locks. | Exact base/head node sets, privacy-safe fixtures, deterministic history/runtime controls, and regression tests. | met |
| V10-R-DOD-03 | The intended V10 accounting, offline-refinalization, early-cleanup, and unauthorized-plan designs remain intact. | Existing focused suites plus scientific-hash and command-pair regressions. | met |
| V10-R-DOD-04 | Independent spec review passes after fixes, and focused smoke passes before and after review. | Reviewer dispositions and rerun results. | met |
| V10-R-DOD-05 | Formatting, Ruff, strict mypy, validation, privacy, portable Quarto/site validation, and `git diff --check` pass; raw pytest is classified against the exact base and the deterministic PR parity check admits no new or missing-base failure. | Exact commands and counts recorded below. | met |
| V10-R-DOD-06 | The same draft PR and branch are updated without rebase, force-push, merge, auto-merge, base mutation, or a new PR; required GitHub Actions passes on the pushed exact head. | Git/PR identities and final Actions run. | pending final push and Actions |

### Root cause and repair

The reviewed implementation promoted V10 identities into shared module globals.
Historical provider entry, qualification, transition, rendering, and cleanup paths
then read the active values instead of a selected historical contract. That could
cause a V3-V9 flow to render a V10 plan/run identity or target resources under the
wrong authority even when the call site was otherwise historical.

`T09ProviderContract` is now a frozen, source-controlled contract with explicit
instances for V3, V4, V5, V6, V7, V8, V9, and V10. Resolution requires an explicit
version; there is no `latest` or default fallback. Provider rendering, loading,
qualification, package transition, image controls, lifecycle budgets, container
ownership, and cleanup consume and cross-bind the selected contract. Cleanup rejects
cross-version ownership and waits for exact absence before replacement eligibility.
V10 selects V10 explicitly. Negative tests prove V3 cannot render V10, V10 cannot
accept V5 authority, cleanup rejects cross-version ownership, stale image contracts
are rejected, and no implicit-current fallback exists.

The CI contract now checks out the exact PR head with full history, selects Python
3.11.14 from `.python-version`, leaves formatting/Ruff/mypy/validation/site strict,
and compares pytest against a detached exact-base worktree under the same interpreter
and dependency closure. Five tests that inspect real user-owned material are marked
`private_local`, default-deny, and symmetrically deselected from base and head parity;
their pure behavior remains covered with public dummy fixtures and privacy canaries.

### Exact failure-set classification

The sets below are exact and avoid duplicating node IDs. The exact base failure set
is `unchanged failing` union `newly passing`. The clean reviewed-head failure set is
the exact-base set minus `base failures already passing at the reviewed head`. The
post-fix failure set is exactly `unchanged failing`.

Unchanged failing (**19**, all category `historical repository failure reproduced on
the exact base`):

```text
tests/test_exp0001_protocol.py::test_exp0001_is_registered_with_incomplete_calibration_and_no_scientific_result
tests/test_exp0001_protocol.py::test_exp0001_validation_rejects_duplicate_task_and_wrong_slice
tests/test_exp0001_protocol.py::test_generic_profile_validator_does_not_impose_sira_conditions
tests/test_exp0001_protocol.py::test_profile_validation_rejects_swapped_order_and_model_drift
tests/test_exp0001_protocol.py::test_profile_validation_rejects_task_source_and_dataset_revision_drift
tests/test_exp0001_protocol.py::test_smoke_and_pilot_profiles_and_condition_plans_validate
tests/test_lambda_ssh_key_fingerprint.py::test_exact_plan_bound_wrapper_loads_hash_bound_source
tests/test_phase1_closeout.py::test_frozen_profiles_are_unauthorized_and_postrun_control_makes_them_nonreplayable
tests/test_phase1_closeout.py::test_phase_one_is_the_only_active_non_executable_control_plane
tests/test_t08_sira_smoke.py::test_pilot_profile_has_explicit_unauthorized_sample_and_budget_contract
tests/test_t09_retry3.py::test_retry3_exact_clean_package_is_host_verifiable
tests/test_t09_retry3.py::test_retry3_plan_has_a_typed_two_slot_raw_first_contract
tests/test_t09_retry3.py::test_retry3_provider_preflight_accepts_source_bound_offhost_runtime_paths
tests/test_t09_retry3.py::test_retry3_same_host_resume_is_disabled_and_slot2_is_source_bound
tests/test_t09_retry3.py::test_retry3_slot2_uses_separate_campaign_and_active_lambda_clocks
tests/test_t09_retry4.py::test_retry4_generated_postfreeze_receipt_admits_first_condition
tests/test_t09_retry4.py::test_retry4_plan_is_typed_science_locked_and_uses_fresh_identities
tests/test_t09_retry5.py::test_autonomous_science_and_zero_retry_identifiers_are_fresh
tests/test_t09_retry5.py::test_retry5_postrun_control_is_archived_while_v8_is_current
```

Newly passing from exact base to repaired head (**37**, category `historical
repository failure directly repaired by the explicit version/source/ownership or
private-fixture contract`):

```text
tests/test_lambda_firewall_baseline.py::test_committed_historical_reports_match_private_structural_analysis
tests/test_lambda_firewall_baseline.py::test_historical_plan_and_run_are_immutable_and_old_v3_fails_closed
tests/test_lambda_firewall_baseline.py::test_historical_projection_is_preserved_but_not_lossless
tests/test_lambda_firewall_baseline.py::test_incident_bundle_seals_without_changing_historical_bytes
tests/test_lambda_inventory_v3.py::test_v1_v2_plans_and_run_0002_ledger_remain_byte_identical
tests/test_lambda_l13_security.py::test_authoritative_l13_consumer_accepts_exact_real_sealed_run
tests/test_lambda_l13_security.py::test_committed_postrun_evidence_is_schema_valid_and_stays_blocked
tests/test_lambda_l23_manual_supervisor.py::test_isolated_bootstrap_loads_repository_source_and_stops_pending_authorization
tests/test_phase1_closeout.py::test_closeout_retains_zero_scientific_interpretation_and_typed_compute
tests/test_phase1_closeout.py::test_historical_status_surfaces_preserve_without_reopening_bounded_v3
tests/test_phase1_closeout.py::test_t07_l1a_plan_is_preserved_and_its_consumed_run_is_sealed
tests/test_sira_container.py::test_arbitrary_host_directories_are_rejected_even_as_read_only_configuration[host_directory1]
tests/test_t07_bounded_supervisor.py::test_exact_local_supervisor_interpreter_loads_bound_modules
tests/test_t07_high_assurance_closeout.py::test_burned_capture_and_scientific_inputs_remain_immutable
tests/test_t07_high_assurance_closeout.py::test_real_private_firewall_scalars_do_not_enter_public_closeout_surfaces
tests/test_t07_high_assurance_closeout.py::test_sealed_private_canonical_v1_remains_valid_under_its_unchanged_schema
tests/test_t09_retry3.py::test_retry3_provider_has_two_distinct_single_use_slots_and_cumulative_caps
tests/test_t09_retry3.py::test_retry3_slot2_transition_and_launch_headroom_are_fail_closed
tests/test_t09_retry4.py::test_retry4_provider_entry_freshness_matches_the_full_preflight_wall
tests/test_t09_retry4.py::test_retry4_slot2_launch_headroom_enforces_exact_active_caps
tests/test_t09_retry5.py::test_retry5_oversized_tree_gets_private_essential_failure_seal[False-0]
tests/test_t09_retry5.py::test_retry5_oversized_tree_gets_private_essential_failure_seal[False-2]
tests/test_t09_retry5.py::test_retry5_oversized_tree_gets_private_essential_failure_seal[True-0]
tests/test_t09_retry5.py::test_retry5_oversized_tree_gets_private_essential_failure_seal[True-2]
tests/test_t09_sira_pilot.py::test_autonomous_clean_descendant_reuses_authority_and_entry_receipt
tests/test_t09_sira_pilot.py::test_autonomous_materialization_policy_is_explicit_and_bound
tests/test_t09_sira_pilot.py::test_autonomous_preflight_and_empirical_lifecycle_boundaries_are_separate
tests/test_t09_sira_pilot.py::test_campaign_lifecycle_uses_actual_elapsed_time_and_preserves_cleanup_reserve
tests/test_t09_sira_pilot.py::test_execution_schema_and_all_static_file_bindings_resolve
tests/test_t09_sira_pilot.py::test_finalizer_validates_canonical_raw_name_not_runtime_mount_alias
tests/test_t09_sira_pilot.py::test_first_pair_checkpoint_passes_only_strictly_below_every_threshold
tests/test_t09_sira_pilot.py::test_independent_selector_specializes_from_frozen_contract
tests/test_t09_sira_pilot.py::test_pragmatic_provider_entry_and_closeout_receipts_are_exact_and_source_bound
tests/test_t09_sira_pilot.py::test_raw_attempt_streams_before_cutoff_without_aggregate_stage
tests/test_t09_sira_pilot.py::test_runtime_identity_binds_every_selected_executable_file
tests/test_t09_sira_pilot.py::test_runtime_qualification_is_typed_slot2_import_preentry_and_digest_agnostic
tests/test_t09_sira_pilot.py::test_t09_provider_is_a_narrow_adapter_over_the_retained_t07_pragmatic_path
```

Base failures already passing at reviewed head `091fa6e...` (**3**):

```text
tests/test_sira_container.py::test_arbitrary_host_directories_are_rejected_even_as_read_only_configuration[host_directory1]
tests/test_t09_sira_pilot.py::test_execution_schema_and_all_static_file_bindings_resolve
tests/test_t09_sira_pilot.py::test_pragmatic_provider_entry_and_closeout_receipts_are_exact_and_source_bound
```

Run `33164854474` differed from the reproducible clean reviewed head by 27 CI-only
failures, all category `environment/version incompatibility`: the old workflow used a
shallow checkout and Python 3.11.16 instead of the frozen full-history Python 3.11.14
closure. Those exact CI-only nodes were:

```text
tests/test_exp0001_protocol.py::test_price_caps_are_exact_conservative_arithmetic_and_unauthorized
tests/test_lambda_inventory_v3.py::test_committed_v3_plan_loads_and_binds_the_frozen_implementation
tests/test_lambda_l20_plan.py::test_scientific_locks_remain_exact
tests/test_lambda_l2m_observer.py::test_locked_science_and_prior_evidence_hashes_remain_exact
tests/test_lambda_ssh_key_archive.py::test_concrete_ssh_key_archive_postcopy_floor_failure_is_not_success
tests/test_lambda_ssh_key_archive.py::test_concrete_ssh_key_archive_stages_finalizes_and_reverifies
tests/test_lambda_ssh_key_executor.py::test_archive_finalize_failure_has_separate_durable_ineligible_disposition
tests/test_lambda_ssh_key_executor.py::test_fake_end_to_end_executor_composes_one_request_ledger_match_and_archive
tests/test_lambda_ssh_key_executor.py::test_response_schema_failure_preserves_completed_response_metadata
tests/test_lambda_ssh_key_executor.py::test_typed_failure_after_send_remains_exact_and_stops
tests/test_lambda_ssh_key_executor.py::test_untyped_failure_after_send_is_durably_unknown_and_stops
tests/test_lambda_ssh_key_fingerprint.py::test_one_request_plan_is_exact_when_committed
tests/test_phase1_closeout.py::test_t07_l13_preserves_all_five_historical_scientific_file_hashes
tests/test_sira_container.py::test_arbitrary_host_directories_are_rejected_even_as_read_only_configuration[host_directory0]
tests/test_sira_container.py::test_arbitrary_host_directories_are_rejected_even_as_read_only_configuration[host_directory1]
tests/test_sira_storage.py::test_locked_exp_0001_scientific_files_did_not_drift
tests/test_t07_bounded_openai_secret.py::test_main_abort_cleanup_survives_plan_bound_artifact_drift
tests/test_t07_bounded_openai_secret.py::test_science_model_and_all_v2_limits_are_unchanged
tests/test_t07_bounded_smoke.py::test_historical_plan_schema_is_valid_but_runtime_binding_is_stale
tests/test_t07_bounded_smoke.py::test_locked_scientific_files_remain_exact
tests/test_t07_bounded_smoke.py::test_valid_plan_is_exact_and_schema_valid
tests/test_t07_pragmatic.py::test_runtime_preflight_executes_artifact_budget_command_and_cleanup_paths
tests/test_t09_provider_accounting.py::test_26_launch_package_command_hash_exception_is_exact_and_source_bound
tests/test_t09_retry3.py::test_retry3_local_qualification_preserves_the_venv_launcher
tests/test_t09_retry4.py::test_retry4_active_slot2_entry_transition_is_source_bound
tests/test_t09_retry4.py::test_retry4_slot2_control_repair_is_a_science_locked_descendant
tests/test_validation.py::test_repository_contract_passes
```

Three artifact-free reviewed-head failures did not appear as Actions failures because
the old workflow skipped or masked their local-runtime dependency. They are category
`private/local-only test with an invalid CI contract`; they now use deterministic
public fixtures or explicit opt-in local coverage:

```text
tests/test_lambda_l13_security.py::test_authoritative_l13_consumer_accepts_exact_real_sealed_run
tests/test_lambda_l23_manual_supervisor.py::test_isolated_bootstrap_loads_repository_source_and_stops_pending_authorization
tests/test_t07_bounded_supervisor.py::test_exact_local_supervisor_interpreter_loads_bound_modules
```

### Verification evidence

- Provider/receipt/cleanup/V10-plan/CI-parity focused matrix: **111 passed**.
- Exact V9 12-call release-order regression: passed three separate invocations; each
  invocation itself executes three consecutive release-order runs and ends with 12
  terminal reconciliations, an exactly empty reservation set, and positive exact
  zero call/token/cost projections.
- Dedicated privacy and secret-canary matrix: **10 passed**.
- Independent source-level specification review: `SOURCE-LEVEL REVIEW-PASSED`.
- Independent regenerated-closure review: `CLOSURE REVIEW-PASSED`; 15 focused closure
  tests passed, all 22 source hashes resolve to implementation commit
  `a5daa11db99229e347008a6110e9ca0a9b7b948d`, and both command pairs rerender exactly.
- Formatting and Ruff: passed. Strict mypy: passed across 64 source files.
  `make validate`: passed. `git diff --check`: passed.
- Portable Quarto 1.9.38 `make site`: passed, including site validation.
- Raw post-fix pytest on repaired implementation head
  `8f0d075d56e6ef640397e59fd962e667c80c5ffe`: **1,578 passed, 19 failed, 5
  skipped**. The installed-package `make check` reproduced the same counts in 38.64
  seconds and stopped at pytest, as
  expected for the inherited raw failure set; it did not reach its later validation
  and site recipes. Those gates were run separately and passed.
- Exact-base comparator at repaired implementation head
  `8f0d075d56e6ef640397e59fd962e667c80c5ffe`: base **1,452 passed / 56
  failed**; head **1,578 passed / 19 failed**; **0 newly
  failing**, **37 newly passing**, **19 unchanged failing**, **0 missing base
  failures**; `parity_passed: true`.

### Rebound unauthorized V10 closure

The repaired implementation is commit `a5daa11db99229e347008a6110e9ca0a9b7b948d`
(tree `62be75facb8fe949a1e3f72b2f682b66a0cad37e`). The V10 closure was regenerated
and committed separately at `1e38a9ad38455ed8e2d9529e2802183b3b2d387b`.

- Runtime identity SHA-256:
  `0f818aeaa7c0f2e309d0e04a8e5c365269442a0bd08969017fe6c6e9d15883eb`.
- Execution-contract SHA-256:
  `41810898f2a10a2d328a4d82d338a3a65634c9031e2304a082c1baa50c004e62`.
- Command-manifest SHA-256:
  `9217db4dda7bbf69911743da70e1aeef0507444a02c480ccc7484ec720383844`.
- `PLAN-EXP0001-PILOT-V10`: **13,426 bytes**, SHA-256
  `17c6502c625e0a3fcabc99180b0a432a60b27557be6a88f3289e45720951b38b`.

The scientific commit, task hashes, dataset commit/blob, evaluator, model, SiRA
revision, condition order, zero-retry policy, timing and budget boundaries, and
descriptive-only interpretation remain unchanged. `authorized`, `execution_allowed`,
`cloud_mutation_allowed`, and `paid_compute_allowed` all remain `false`; qualification,
pilot, and run-root materialization are also false. No V10 identity was consumed.

### First pushed-head CI correction

Actions run `33184598008` on closeout head
`f3597df8f7276d8697999de5d3ed3bfe6103cc5f` passed checkout, Python 3.11.14 setup,
dependency sync, formatting, Ruff, and strict mypy, then failed `make validate` before
pytest with `downstream finalizer history is unavailable`. The disposition binds
historical finalizer commit `d6a080264c7d2ac83efc9806d2a2ae4c141a1113`, but that
object is local historical evidence not reachable from any public GitHub ref; GitHub
returns 404 for the exact object. Full ref history therefore could not make the old
implicit dependency reproducible.

The repair adds
`contracts/T09_V8_DOWNSTREAM_FINALIZER_SOURCE_HISTORY.json`, a tamper-evident closure
with exact frozen/downstream commits, downstream tree, three changed paths, and their
source SHA-256 values. Repository validation requires the closure's exact file hash
and cross-binds its identities and source hashes to the immutable disposition. When
the historical object is locally available it additionally recomputes the tree, diff,
and source hashes; when the object is absent it uses the same exact closure rather
than skipping or weakening the check. The historical runtime test now exercises both
forms, and a negative regression rejects any closure-byte mutation.

### Final local closeout candidate

The ref-independent history repair is committed at
`532592ec764bf4b3fbc5ebede9aae8a757b8ac98`; its explicit unavailable-object
regression is committed at `8f0d075d56e6ef640397e59fd962e667c80c5ffe` (tree
`f7fc02350afdfdff87b87acfbd53432bf2e2f7f7`). On that exact repaired head:

- focused unavailable-object/history/closure validation passed;
- the full installed-package `make check` reached pytest with **1,578 passed, 19
  failed, 5 skipped** after formatting, Ruff, and strict mypy passed;
- the required `make ci-check` passed formatting, Ruff, strict mypy, repository
  validation, portable Quarto 1.9.38 site rendering/validation, and exact pytest
  parity;
- exact parity was base **1,452 passed / 56 failed** versus head **1,578 passed / 19
  failed**, with **0 newly failing**, **37 newly passing**, **19 unchanged failing**,
  **0 missing base failures**, and `parity_passed: true`.

The ledger closeout commit follows this repaired implementation head. The required
post-closeout exact-head local rerun and GitHub Actions conclusion are reported in
the PR body and final handoff, because recording either result in this tracked file
afterward would itself create a different, untested head.

## PR #3 outcome-aware pytest parity remediation

Assembly status: **local-complete; final PR Actions pending**

Reviewed head `1b22ed2aff9c6e3ced1c8a2a6968b5c47ab7d064` retained only collected and
failed-node sets in `ci_pytest_parity.py`. That model could misclassify a base failure
that became skipped, xfailed, or missing as newly passing, and it checked collection
preservation only for base failures. The permanent PR gate could therefore admit
weakened coverage even though its reported failure-set algebra appeared unchanged.

| ID | Required remediation outcome | Planned evidence | Status |
|---|---|---|---|
| V10-PARITY-DOD-01 | Every collected node has one exact, nonduplicated outcome that distinguishes pass, failure, error, ordinary skip, and xfail while retaining exact parameterized node IDs. | Pinned-pytest JUnit integration fixture plus parser identity/count/duplicate regressions. | met |
| V10-PARITY-DOD-02 | Comparison admits only the specified improvements and fails closed on new failures, missing base nodes, and passed/failed base nodes weakened to skip or xfail. | Focused transition-table regressions and deterministic schema-versioned comparison output. | met |
| V10-PARITY-DOD-03 | The five existing private/local node IDs are the only symmetric exclusions, applied identically to base and head with environment-based broadening disabled. | Command/environment helper regressions and exact-list assertion. | met |
| V10-PARITY-DOD-04 | Provider/scientific/cleanup behavior and V10 authorization state remain unchanged. | Scope diff, existing focused controls, validation, and unchanged plan flags. | met |
| V10-PARITY-DOD-05 | Focused smoke, independent source review, post-review smoke, raw suite, static gates, site gate, and exact detached-base/head parity all satisfy the repair contract. | Exact commands and counts recorded at closeout. | met |
| V10-PARITY-DOD-06 | The existing draft PR and branch advance normally to one exact head with successful required Actions; no merge, auto-merge, rebase, or force-push occurs. | Remote/PR identities and final Actions run recorded outside the pre-CI commit. | partial: final closeout commit, push, and Actions pending |

Implementation mapping is intentionally narrow: `ci_pytest_parity.py` and its
focused tests satisfy V10-PARITY-DOD-01 through V10-PARITY-DOD-03; this ledger and
the existing repository gates satisfy V10-PARITY-DOD-04 through
V10-PARITY-DOD-06. Provider contracts are not reopened.

### Repaired comparator contract

Comparison schema `2.0.0` records one immutable `(node_id, status)` pair for every
collected node. The statuses are `passed`, `failed`, `error`, `skipped`, `xfailed`,
and exposed strict `xpassed`; exact class and parameterized IDs are reconstructed
from pinned pytest 8.4.2 legacy JUnit. Missing identities, duplicate identities,
contradictory children, unknown skip forms, and inconsistent suite counts fail
closed. The parser also models pytest's valid pass-then-teardown-error phase count
without mistaking the extra phase count for a second collected node.

Only base `failed`/`error` to head `passed` is `newly_passing`. Base
`failed`/`error` to head `failed`/`error` remains `unchanged_failing`; base
`skipped`/`xfailed` to head `passed` is improved coverage. Any head failure not
inherited from a failing base node is newly failing. Every missing base-collected
node fails parity. Any executed base node weakened to head `skipped`/`xfailed`
fails parity. Head-only pass, skip, or xfail does not masquerade as a repaired base
failure.

The exact five pre-existing private/local node IDs remain the only deselections and
are passed literally and identically to both commands. `GICLAB_RUN_PRIVATE_T09_TESTS`,
`PYTEST_ADDOPTS`, and `PYTEST_PLUGINS` are removed and plugin autoload is disabled in
both parity environments. The gate resolves the exact base and expected-head commits,
requires a clean head checkout including untracked files, and checks removal of its
exact detached base worktree. Failed or interrupted materialization also removes any
partial exact registration; cleanup failures are surfaced without masking the primary
failure.

### Pre-commit verification

- `PYTHONPATH=src uv run --no-sync pytest -q tests/test_ci_pytest_parity.py`:
  **33 passed** after the independent review fixes. The post-discovery focused
  matrix added the two restored cleanup nodes and passed **35 tests** total.
- Independent source/spec review: **REVIEW-PASSED** after three passes. It checked the
  complete transition matrix, pinned JUnit teardown and strict-XPASS behavior,
  duplicate/count rejection, exact exclusions and environment, exact commit and clean
  head selection, and successful, failed, and partially registered worktree cleanup.
- Repository formatting: **159 files unchanged**. Ruff: **passed**. Strict mypy:
  **passed across 64 source files**. `make validate`: **passed**. `git diff --check`:
  **passed**.
- Portable Quarto 1.9.38 `make site`: **passed**, including site validation.
- Raw full pytest under Python 3.11.14 with the normal private-test policy, using a
  local high-free-space scratch filesystem mounted under the normal macOS temp path
  so both path and prewrite-floor semantics were preserved: **1,608 passed, 19
  failed, 5 skipped in 58.97s**. `make check` separately reproduced **1,608
  passed, 19 failed, 5 skipped in 58.64s** after
  lock, sync, formatting, Ruff, and mypy passed, then stopped at the inherited pytest
  failures as expected. Validation and site were run separately and passed.
- Exact committed-base/head `make ci-check` at implementation head
  `978449d3e625ed6a40c464a6c29edce21a8d2577`: **passed**. The exact base
  `503def0519e36f04b62b16158c72e11213b3bf9f` produced **1,452 passed / 56
  failed** across 1,508 collected nodes. The head produced **1,608 passed / 19
  failed** across 1,627 collected nodes. There were **0 newly failing**, **37 newly
  passing**, **19 unchanged failing**, **0 missing base-collected nodes**, **0
  invalid/weakened transitions**, and **0 skip, xfail, xpass, or error outcomes** in
  either parity run; `parity_passed: true`.

The first clean implementation check at
`a67d54c2d487e0b2ad79213e9a6597ab881481c3` correctly returned
`parity_passed: false` because these two passing base nodes had been renamed during
the earlier version-contract repair:

```text
tests/test_t09_retry5.py::test_retry5_cleanup_rejects_unacknowledged_raw_before_any_destructive_action
tests/test_t09_retry5.py::test_retry5_cleanup_requires_started_reservation_recovery_before_destruction
```

They were restored as executable active-V10 regressions, not aliases, skips, or
exclusions. The first proves an unacknowledged raw attempt blocks cleanup before
Docker or secret destruction; the second proves a started reservation requires
recovery before destruction. Their shared helper now receives an explicit immutable
provider contract and retains V8 as its default. Independent rereview found no
provider/cleanup weakening and **REVIEW-PASSED** the restoration.

The exact 19 raw inherited failures are:

```text
tests/test_exp0001_protocol.py::test_exp0001_is_registered_with_incomplete_calibration_and_no_scientific_result
tests/test_exp0001_protocol.py::test_smoke_and_pilot_profiles_and_condition_plans_validate
tests/test_exp0001_protocol.py::test_profile_validation_rejects_swapped_order_and_model_drift
tests/test_exp0001_protocol.py::test_exp0001_validation_rejects_duplicate_task_and_wrong_slice
tests/test_exp0001_protocol.py::test_profile_validation_rejects_task_source_and_dataset_revision_drift
tests/test_exp0001_protocol.py::test_generic_profile_validator_does_not_impose_sira_conditions
tests/test_lambda_ssh_key_fingerprint.py::test_exact_plan_bound_wrapper_loads_hash_bound_source
tests/test_phase1_closeout.py::test_phase_one_is_the_only_active_non_executable_control_plane
tests/test_phase1_closeout.py::test_frozen_profiles_are_unauthorized_and_postrun_control_makes_them_nonreplayable
tests/test_t08_sira_smoke.py::test_pilot_profile_has_explicit_unauthorized_sample_and_budget_contract
tests/test_t09_retry3.py::test_retry3_same_host_resume_is_disabled_and_slot2_is_source_bound
tests/test_t09_retry3.py::test_retry3_slot2_uses_separate_campaign_and_active_lambda_clocks
tests/test_t09_retry3.py::test_retry3_exact_clean_package_is_host_verifiable
tests/test_t09_retry3.py::test_retry3_plan_has_a_typed_two_slot_raw_first_contract
tests/test_t09_retry3.py::test_retry3_provider_preflight_accepts_source_bound_offhost_runtime_paths
tests/test_t09_retry4.py::test_retry4_plan_is_typed_science_locked_and_uses_fresh_identities
tests/test_t09_retry4.py::test_retry4_generated_postfreeze_receipt_admits_first_condition
tests/test_t09_retry5.py::test_autonomous_science_and_zero_retry_identifiers_are_fresh
tests/test_t09_retry5.py::test_retry5_postrun_control_is_archived_while_v8_is_current
```

The diff remains limited to this ledger, `src/giclab/ci_pytest_parity.py`,
`tests/test_ci_pytest_parity.py`, and the necessarily restored nodes in
`tests/test_t09_retry5.py`. `PLAN-EXP0001-PILOT-V10` remains 13,426 bytes with
SHA-256 `17c6502c625e0a3fcabc99180b0a432a60b27557be6a88f3289e45720951b38b`.
`authorized`, `execution_allowed`, `cloud_mutation_allowed`,
`paid_compute_allowed`, `live_qualification_performed`, `pilot_executed`, and
`empirical_run_roots_materialized` all remain false. No Lambda, model/provider,
secret, cloud, browser, Docker, SiRA, FanOutQA, evaluator, scientific-condition, or
pilot execution occurred.

This ledger closeout commit follows the verified implementation head. The required
post-closeout exact-head local rerun and GitHub Actions identifiers are recorded in
the PR body and final handoff rather than backfilled into a commit that predates
those executions.

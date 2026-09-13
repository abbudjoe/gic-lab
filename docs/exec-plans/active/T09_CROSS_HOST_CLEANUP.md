# Phase 1 — T09 shared cross-host cleanup repair

Status: **in-progress**

Plan role: **workstream**

Assembly status: **in-progress**.

## Source contract and scope

Governing owner instruction: `GIC_T09_CROSS_HOST_CLEANUP_PUBLICATION_AND_CENSUS_REPAIR.md`,
2026-09-12, sections 1–19. Base `0aec49c0975dd39b29800f981434008788f254d6`,
tree `852e16d25f240b924240d75022939f71ee5a9edb`.
Private blocker commit `501083857f0bfa1ddda4648952282ac383b16082`,
manifest `cda46a9ae082916d3f148c5fa8e5f5dc21f4c161ea5530c1e4e338a4ff742286`.

In scope: shared controller-owned remote cleanup binding, finite grants, provider
namespace metadata observer, complete bounded census, combined reconciliation,
offline validation, one draft PR and one private exact-head handoff.
Out of scope: V17 generation/activation, live effects, real credentials, spending,
scientific execution/interpretation, shared runtimes, ready-for-review and merge.
The historical blocked V17 branch remains untouched and is not an ancestor.

## Definition of done and acceptance map

Each grouped row below retains every case in section 12 of the source contract.
Exact node mappings below use test functions with their complete parameter sets;
unrun validation remains explicitly pending.

| ID | Contract / required cases | Production / test mapping | Status |
| --- | --- | --- | --- |
| CH-01 | Exact base, merged PR 15, disabled workflows, preserved clean V17 | Git/GitHub preflight | met |
| CH-A | Four legacy namespace and copied-publication characterizations | campaign_output.py; test_cross_host_cleanup_boundary.py | met |
| CH-B | Exact binding; reject wrong provider, slot, plan/run, transfer, source/candidate, root, handoff/attempt, unsafe member, duplicate/reordered/replayed sequence and foreign grant/observation | remote binding/protocol; test_remote_cleanup.py | met |
| CH-C | Pregrant create denial, create/partial/excess writes, deny/no-byte, append continuity, temporary replacement, changed retirement inode, retained temporary, exact removal, disconnect/no-refund, reserve exhaustion and terminal denial | production accountant and remote grant state; test_remote_cleanup.py | met |
| CH-D | Root/component symlink, hardlink, nonregular, owner/mode, device escape, root/inode change, descriptor/path mismatch, original deadline and teardown | retained remote observer; test_remote_cleanup.py | met |
| CH-E | Complete before/after; new/changed unadmitted member, omitted publication/member, duplicate/count/total/retirement/removal/delta errors, incomplete/entry/depth/frame caps; independent remote proof and separate export equality | remote census reconciliation; test_remote_cleanup.py | met |
| CH-F | Joined success, denial, partial/disconnect, unadmitted growth, bounded resume, wrong binding/root, terminal ACK loss, exact zero/security/descriptors; preserve 53 rows and 37 joined parameters | production cleanup and retained offline effects; test_cross_host_cleanup_joined.py | partial |
| CH-G | V3–V16 source-context validation; V16 disposition, no V17, local protocol compatibility, normal receipts, explicit dispatch | historical/control validation nodes | partial |
| CH-08 | Non-circular frozen implementation/test ancestor and required receipt descendants | source identity and normal receipt generation | partial |
| CH-09 | Exact base/head pinned isolated local gate; five symmetric deselections, no regressions or weakened transitions; static/control/schema/receipt/privacy/site | make ci-check; full JUnit/per-node/parity | partial |
| CH-10 | Verified export and exact-owned closeout; one draft PR and private read-back handoff | pinned publication/access/manifest checks | not-started |

## Evidence and decisions

- Remote base/tree/parents and merged PR 15 verified; both workflows disabled manually.
- Local destination reference is a historical ancestor, not remote branch drift.
- New repair worktree created directly at the exact merged base.
- Blocked V17 checkpoint is clean at `70ac0f84cc5040638a8edcbf5e3526bb338dcbd1`,
  tree `88ef05ad661564aaced14021baad1b38ab38d563`; it remains local and untouched.
- Required blocker evidence read from its pinned private commit; manifest hash verified.
- Four characterization cases selectively ported; no V17 ledger or adapter copied.
- Approved CI locator hash verified; bound external volume identity and capacity checked.
- Source/component runs passed 35, 62, 66, 75 and 86 nodes as coverage expanded.
- Run `gic-pr15-ci-8a38dffac47cbca9` passed all 326 nodes in the grouped
  cross-host, characterization and remote-transaction review selection.
- Review found and corrected publication-chain and controller-deadline defects.
  Run `gic-pr15-ci-8815776a54fafd45` passed 332 nodes and failed one new denial
  fixture because it expected the wrong exception type. The actual denied writer
  wrote no byte. The fixture now checks the existing precise budget exception.
- Every attempted run, including red diagnostic/export results, is retained privately.
  The 86-node run's exporter encountered pytest aliases after tests passed; exact
  stopped-container recovery verified all original files before owned cleanup.
- A final invariant audit found direct/cached condition-accountant access could
  bypass the normal lifecycle stop after ambiguous cleanup. Unresolved remote
  cleanup now blocks shared non-cleanup admission and both new/cached condition
  access; cleanup reserve is retained for closeout. Joined disconnect regression
  checks no further publication or reserve change.
- Resume-census audit: local activity before a sequence-zero interruption cannot
  become a new baseline. Resume now requires no local lease and an unchanged local
  census; unresolved sessions are rejected before another effect invocation.
- Strict wire identity rejects bool/float aliases for bound integer fields and
  response sequences. Legacy local wire forms remain unchanged.
- Run `gic-pr15-ci-78b3a6e55407ecc9` passed all 403 grouped source/controller/
  historical package-verifier nodes, including all 37 preserved joined parameters;
  9,766 exported files were verified before exact-owned container/volume cleanup.
- Final post-review run `gic-pr15-ci-066efcd65f20ab1f` passed all 339 nodes,
  including the final ambiguity, pristine-local resume and numeric wire regressions.
  No failures, errors or skips occurred; export and owned cleanup were verified.
- Subagent spec-conformance rereview has no outstanding actionable findings.
  It does not replace the independent exact-head review required after delivery.
- CH-F remains partial only for the complete 53-row exact-head audit; CH-G awaits
  normal current receipt generation and the complete historical base/head gate.
- Pinned static run `gic-pr15-ci-2a13af7f69cd165b` passed lint/type checks but
  exposed the workstream's missing typed plan header. The header is now corrected.
  Its contract validation also correctly rejected old current V16 receipts after
  shared source changes; normal regeneration must follow the frozen ancestor.
  Pre-freeze static validation therefore covers lint/types/site; receipt/control
  validation remains mandatory in the unchanged complete final gate.
- Final-gate and scientific results are not claimed in this source-freeze record.

## Exact-gate regression and renewed freeze

Assembly status for CH-09: **scout-pending**; root-cause repair and review complete.
The first frozen ancestor `d7af19004072a8154523e0c28f0c873865af8da2` and normal
receipt descendant `71eeb39d136e31312c56573ac8a2d043a23dfe7f` remain immutable.
An initial gate stopped on an unreproduced historical 90-second watchdog timeout;
its unchanged three-case reproduction passed. Complete run
`gic-pr15-ci-48dbd3524cc50952` then recorded all 115 new nodes passing, raw base
2932 passed / 28 failed / 2 skipped and raw head 3048 passed / 27 failed / 2 skipped.
It correctly failed parity for one newly failing historical offline-guard node:
the base and head inherited the same `TMPDIR`, so the base's deliberately
unregistered directory collided with the head before its guard assertion.
All original outcomes and verified exports are retained; no exclusion changed.

The parity launcher now allocates and validates a private temporary namespace for
each sequential side, separate from pytest basetemp. The trusted parent narrows
`TMPDIR`/`TMP`/`TEMP` and the tempfile cache before the unchanged guard propagates
parent storage to descendants. Original parent state is restored on every exit;
side allocations remain owned by enclosing evidence/runtime cleanup. Private
execution records bind each namespace's path, device/inode, owner and mode.
No image, guard permission, historical assertion, test selection or timeout changes.
The regression runs the unchanged historical guard test twice and checks inherited
storage, distinct identities, unsafe allocation rejection and restoration on errors.
Mapped source: `src/giclab/ci_pytest_parity.py`; tests:
`tests/test_ci_pytest_parity.py::test_sequential_parity_runs_own_temporary_storage_and_preserve_guard`,
`test_parity_rejects_unsafe_temporary_namespace_before_child`, and
`test_parity_restores_parent_storage_on_error_or_root_substitution`.
Run `gic-pr15-ci-e12493ee017b9251` passed 83 CI ownership/guard tests. Review
then identified initially-unset tempfile-cache restoration and failure-path evidence
gaps; both were fixed and rereviewed without outstanding findings. Run
`gic-pr15-ci-2f8db6d6027d70f2` passed all 426 expanded focused nodes in 58.561
seconds, with zero failures, errors or skips. Additional regressions are
`test_parity_restores_initially_unset_tempfile_cache` and
`test_parity_retains_execution_evidence_on_launch_or_namespace_failure`.
Pinned static run `gic-pr15-ci-8d37004d9094f469` passed type/site checks and
rejected only new regression-fixture style errors. The literal concatenation and
context-manager layout were corrected and rereviewed with no semantic concerns;
exact-byte focused/static reruns are required before renewed freeze.
A new normal implementation ancestor, normal receipt regeneration and the complete
exact-base/head gate remain required. The original 115 new nodes, all 53 accepted
rows and all 37 historical joined parameters passed in the retained red full run;
that does not turn its failed parity result into a pass.

## Topology and next permitted phase

Exact base → green implementation/test ancestor → normal required receipt descendants
→ exact validated candidate. No amend/rebase/reset/force-push/no-op identities.
Next: complete pinned static validation, freeze the reviewed green implementation,
generate normal current receipts, and run the exact base/head gate. Publication
requires CH-09. Stop after the one
private handoff for independent exact-head review. No Category 3 authority is granted.
This file records the source-freeze state. The exact-head handoff resolves the
remaining receipt, final validation and delivery rows with immutable evidence;
validation results cannot be asserted before the candidate they validate exists.


## Finite claim-to-node map

All paths in this map are repository relative. `R` means
`tests/control/test_remote_cleanup.py`, `J` means
`tests/control/test_cross_host_cleanup_joined.py`, and `B` means
`tests/control/test_cross_host_cleanup_boundary.py`. Each function below includes
all declared parameter values. The private handoff retains full expanded node IDs,
source manifests and per-node outcomes, including failed development attempts.

| Row | Contract cases | Production source | Test functions |
| --- | --- | --- | --- |
| A1–4 | Local namespace rejects remote roots; copied bytes cannot prove remote publication | campaign_output: local binding, authority, inode verifier; production: writer scope | B: all four `test_*` functions |
| B1 | Exact accepted transfer binding and combined successful cleanup | production: `_remote_cleanup_authority`, `cleanup` | J: `test_joined_controller_remote_and_local_publication_one_accountant` |
| B2 | Wrong provider, slot, plan/run, transfer, source commit/tree/candidate, root, handoff/attempt, nonce/helper/contract | remote_cleanup: binding and authority handshake | R: `test_binding_substitution_before_effect` |
| B3 | Absolute, traversal, empty, noncanonical or over-depth members | remote_cleanup: `member` | R: `test_remote_members_are_canonical_relative_posix` |
| B4 | Foreign binding; duplicate/reordered/replayed sequences and snapshot phases | remote_cleanup: authority phase/sequence checks | R: `test_wrong_initial_sequence`, `test_census_phase_replay_fails_closed`, `test_binding_substitution_before_effect`, `test_binding_numeric_aliases_cannot_bypass_canonical_identity`, `test_response_sequence_requires_exact_integer_type` |
| C1 | No create without grant; exact create, append, replacement, removal | remote_cleanup: grant/open/temporary/write/verify transitions and observer | R: `test_open_event_without_grant_is_rejected_before_effect`, `test_actual_separate_process_create_append_replace_remove_and_census` |
| C2 | Partial actual write, no refund, oversize request rejected | remote_cleanup: observer publication and authority grant/write accounting | R: `test_successful_partial_admitted_write_never_refunds`, `test_payload_exceeding_requested_grant_is_rejected_before_open` |
| C3 | Denial and exhausted cleanup reserve write no byte; shared terminal denial blocks later writers and conditions | production: shared reserve, writer and condition admission | R: `test_fail_closed_denial_disconnect_unadmitted`; J: `test_joined_remote_denial_blocks_subsequent_noncleanup_writer` |
| C4 | Append inode continuity; exact retiring inode; admitted temporary and zero-byte operations | remote_cleanup: observer and verify transition | R: `test_actual_inode_substitution_after_grant_fails_before_write`, `test_zero_byte_operations_bind_real_inodes`, `test_faulted_observations_do_not_reconcile` |
| C5 | Interrupted temporary and partial writes retained; disconnect cannot refund/restart | remote_cleanup: unresolved disposition; production: retained sessions | R: `test_actual_partial_write_disconnect_retains_grant_and_temporary`; J: `test_joined_partial_disconnect_cannot_resume_or_refund` |
| C6 | Exact baseline removal versus newly created/replaced removal lineage | remote_cleanup: live baseline and occupancy equation | R: `test_removal_provenance_distinguishes_baseline_from_new_bytes` |
| D1 | Symlink root/component, hardlink, nonregular target, unsafe mode | remote_cleanup: no-follow descriptor traversal and metadata validation | R: `test_actual_root_and_parent_symlinks_are_never_followed`, `test_actual_unsafe_or_unadmitted_files_fail_terminal_census` |
| D2 | Owner/device escape where non-root injection is required | remote_cleanup: metadata validation | R: `test_unsafe_metadata_fault_injection_for_nonroot_properties` |
| D3 | Root/parent rename, inode substitution, descriptor/path mismatch, occupied fresh inode | remote_cleanup: held root/parent and opened/temporary validation | R: `test_actual_root_substitution_is_rejected`, `test_actual_parent_rename_cannot_use_held_descriptor`, `test_actual_opened_descriptor_name_mismatch_is_rejected`, `test_faulted_fresh_inode_cannot_reuse_occupied_member` |
| D4 | Original deadline, independent clock epochs, response transit, actual helper teardown | remote_cleanup: channel deadline and observer checks | R: `test_original_deadline_is_not_renewed`, `test_provider_clock_epoch_and_response_transit_do_not_extend_deadline`, `test_actual_helper_deadline_expires_with_bounded_process_teardown` |
| E1 | Complete bounded census independently equals actual filesystem | remote_cleanup: snapshot and controller reconciliation | R: `test_actual_separate_process_create_append_replace_remove_and_census`, `test_largest_supported_complete_before_after_census` |
| E2 | Unadmitted new/changed members and unexplained growth | remote_cleanup: expected inventory equality and byte equation | R: `test_actual_unsafe_or_unadmitted_files_fail_terminal_census`, `test_fail_closed_denial_disconnect_unadmitted` |
| E3 | Omitted publication/baseline, duplicate member, bad count/bytes/digest, incomplete census, wrong retirement/inode | remote_cleanup: snapshot-end and verification | R: `test_faulted_observations_do_not_reconcile`, `test_omitted_baseline_with_consistent_forged_snapshot_totals_is_rejected` |
| E4 | Entry/depth/frame limits fail without truncation | remote_cleanup: finite traversal/framing | R: `test_bounded_census_and_frame_fail_without_truncation`, `test_largest_supported_complete_before_after_census` |
| E5 | Local copy without proof rejected; remote proof requires no copy; selected export equality is downstream fact | campaign_output local verifier; remote_cleanup observer | B: `test_shared_verifier_requires_actual_local_publication_not_remote_byte_report`; R: `test_remote_proof_and_local_export_are_separate_facts` |
| E6 | Canonical structural protocol and explicit historical receipt forms | schema and remote_cleanup; effects extension subclasses | R: `test_canonical_protocol_schema_validates_real_observations`, `test_explicit_legacy_and_remote_cleanup_receipt_forms`, `test_legacy_channel_protocol_is_separately_versioned` |
| F1 | Shared local/remote accountant and complete controller decision | production: cleanup and local census | J: `test_joined_controller_remote_and_local_publication_one_accountant` |
| F2 | Denial, disconnect/partial write, unadmitted remote/local growth, wrong root/receipt, missing proof, ACK loss | production: cleanup terminal validation | J: `test_joined_controller_negative_paths_preserve_unresolved_authority` |
| F3 | Original deadline/binding/reserve reused before handshake; ambiguous observed session cannot resume | production: retained original deadline and sessions | J: `test_joined_cleanup_resume_reuses_original_deadline_binding_and_reserve`, `test_joined_partial_disconnect_cannot_resume_or_refund`, `test_joined_local_activity_before_handshake_cannot_become_resume_baseline` |
| F4 | Local create→append/replacement causal identity and deadline-aware controller traversal | production: terminal local lease validation; campaign_output: inventory callback | J: `test_joined_repeated_local_publication_validates_causal_chain`, `test_joined_controller_census_enforces_original_deadline` |
| F5 | Existing R3/R5/R6 release, exact zero/security, retained process/descriptor and 53-row/37-parameter matrix preservation | existing production/effects/bridge carriers | `test_remote_transaction_review.py`, `test_production_coupling.py`, `test_live_method_viability.py`, `test_candidate_inputs.py::test_candidate_actual_package_verifier_in_isolated_source_process` |
| G1 | V3–V16 source contexts, V16 consumed-prelaunch state, explicit dispatch, no V17 | existing registry/package binding and agent validation | full `make ci-check`, normal `refresh-receipts`, source/science projection |

The new local census callback is opt-in for joined cross-host cleanup; historical
local callers retain their original traversal and verifier semantics. Intermediate
local leases must already be verified before another publication supersedes them;
only the terminal lease is checked against the live file. No verification is
fabricated retrospectively for an intermediate publication.

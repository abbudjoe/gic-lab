# T07 Gate L2.3 implementation ledger

Status: **validated; independent review clean; ready for manual-console qualification authorization; executable plan remains unauthorized**

Date: 2026-08-11

Source contract: the user-supplied
`T07_GATE_L2_3_DECISION_BINDING_AND_MANUAL_PLAN.md`.

Reviewed implementation commit:
`e2b0cb93bba03599f128621f537c2f6255bae2c8`.

This ledger maps the Gate L2.3 definition of done to implementation and evidence. It
does not grant execution authority. No account/model request, credential access,
console mutation, paid compute, SSH, Jupyter, image pull, container, browser, SiRA or
scientific execution is permitted by this record.

| ID | Definition-of-done item | Status | Evidence |
|---|---|---|---|
| L23-01 | Verify exact branch, clean starting commit, L2.2 ancestor/bundle hashes, sealed prior evidence, zero known running instances, locked science and zero-secret requirement before reading the decision. | met | Read-only Git/hash/schema/storage checks at clean `b71cbbc29f59da600d57b7f0ad28d14572b5fc62`; exact paths and locked hashes recorded in the decision-binding report. |
| L23-02 | Open the private decision with owner/mode/regular/single-link/no-follow checks and enforce its schema, nonce, globally routable `/32`, every true attestation and exact selected caps/resources. | met | `lambda_l23_manual_plan.py` typed validator plus negative tests; 1,505-byte decision validated without printing a private field. |
| L23-03 | Seal the original decision, canonical identity and schema result locally; expose only opaque alias/hashes. | met | Decision alias `l2m-decision-6b7af4f2c567`; source/canonical/seal hashes in the decision-binding report; raw values remain ignored and mode-restricted. |
| L23-04 | Copy the private seal one-way to the approved external archive, verify source/destination hashes, fsync/atomically finalize, retain source and forbid internal fallback. | met | Public copy/seal hashes `3436784…b1c2d` and `5b1fea4…9f95`; archive/storage guard used held no-follow descriptors and exact UUIDs. |
| L23-05 | Privately resolve image, SSH-key unique match, global firewall, `/32`, marker, checkpoint, run and archive identities from sealed evidence only. | met | Ignored `private-parameters.json` is bound by SHA-256 `cfd40a…6f6b6`; public plan contains only aliases/hashes. |
| L23-06 | Require a non-mutating launch-wizard offeredness checkpoint before every firewall mutation. | met | Checkpoint 01, step 2, lifecycle ordering and mismatch regressions stop before mutation. |
| L23-07 | Encode exactly 23 ordered actor steps separating user console/Jupyter actions, GET-only observer actions and one host-bundle command. | met | Rendered public plan plus exact sequence validator and actor/order mutation tests. |
| L23-08 | Use exactly 13 fresh single-use private user checkpoints; make instance binding and terminal proof observer-only durable receipts. | met | Checkpoint schema/templates, held challenge/checkpoint descriptors, fsync consumption ledger and supervisor receipt code. |
| L23-09 | Implement an exact-source isolated supervisor bootstrap and preflight binding branch/commit/plan/artifacts/private seals/storage/caps/SSH public fingerprint before credential access. | met | `l23_supervisor_bootstrap.py` plus plan/supervisor tests; expiry and every mismatch fail before credential/network. |
| L23-10 | Enforce GET-only in-process observation with exact endpoint/phase/call/byte/time/journal limits and zero shell HTTP or automated mutation. | met | Observer integration in the supervisor; 44-GET partition, durable reservation and fake-transport tests; no mutation method exists. |
| L23-11 | Bind exactly one launch through the unique owned ruleset and exact tuple; stop workload on zero/multiple/drift and permit no second click. | met | Nine-poll bounded binder, observer-only exact binding receipt and ambiguity/no-replay tests. |
| L23-12 | Keep cleanup authority explicit: ruleset-attached private IDs only; unattached/unknown rows preserve strict firewall and require a new human decision. | met | Typed incident scope and terminal verifier; adversarial unattached-row tests. |
| L23-13 | Validate success/failure archives through held inbound bytes; bind the already-written download checkpoint; never rerun qualification. | met | Supervisor archive waiter/validator and success/failure/absence/path-swap regressions. |
| L23-14 | Require terminal/absence before owned-ruleset deletion and ruleset absence before exact original-global restoration. | met | Lifecycle state machine, observer-only terminal receipt, semantic firewall hash and cleanup-order tests. |
| L23-15 | Preserve strict firewall and residual billing evidence on control-plane outage; burn the run after observer restart and never broadly prune/delete. | met | Closed incident states and runbook/plan incident rules; cleanup targets only exact private ownership identities. |
| L23-16 | Bind all exact numeric provider, observer, checkpoint, process, Docker, output, evidence and storage caps from L2.2 without stale phase counts. | met | Public plan/packet; phase counts `6+1+1+1+9+0+0+10+2+1+13=44`; cap equality tests. |
| L23-17 | Bind exact immutable schemas, bundle, source observation, implementation artifacts and hash-first qualification argv. | met | Plan artifact table and validator; manifest `dc9824…c261`, driver `ab9a3f…5050`, exact argv regressions. |
| L23-18 | Preserve the exact EXP-0001 scientific contract and keep Gate L3/L4/pilot/training/interpretation unauthorized. | met | Locked-file hash tests and public plan `scientific_lock`; no scientific file changed. |
| L23-19 | Render a fresh executable but unauthorized plan/run with exact bytes/hash and expiry. | met | Plan V1/run 0001, 21,638 bytes, SHA-256 `2b2302…2f99b`; every authority Boolean false; latest start `2026-08-12T05:15:19.646016Z`. |
| L23-20 | Create decision report, ledger, packet, exact runbook, manual-console README and update all required governance/public surfaces. | met | Required files plus project state, policy/test, active plan, D-029, readiness, Gate L3 requirements, Lambda/harness READMEs and sanitized notebook note. |
| L23-21 | Preserve all prior plans/evidence and avoid every prohibited live action/private disclosure. | met | Prior Git/evidence paths unchanged; public privacy checks contain aliases/hashes only; no real secret/account/runtime action occurred. |
| L23-22 | Run focused/Lambda/schema/repository/privacy/format/Ruff/mypy/portable-Quarto gates. | met | Focused Gate L2.3 suite: 189 passed; all Lambda suites: 561 passed; final portable-Quarto `make check`: 1,015 tests, repository validation, Ruff, strict mypy and all 16 notebook pages passed. The private-scalar scan examined 42 candidates and found zero public leaks. |
| L23-23 | Obtain independent spec/privacy/cloud-safety/human-factors/incident review, repair findings and rerun the full gate. | met | Independent review identified an incomplete machine-readable cap surface and a stale README distinction. A shared renderer/validator cap contract now binds 81 cap fields, the plan was rerendered and the README repaired. Final rereview found no P0/P1/P2 issue and independently verified 31 bound artifacts, all authority flags false and privacy-clean output. |
| L23-24 | Commit on `phase-1/sira-smoke-lambda`, leave the worktree clean and stop before authorization/execution. | met | Satisfied by the terminal handoff commit and clean-status proof reported outside this self-referential ledger; no authorization or execution is included in that commit. |

## Assembly boundary

All Gate L2.3 definition-of-done items are met. The terminal handoff state is
`ready-for-manual-console-qualification-authorization`. The plan remains unauthorized
and unexecuted until the user sends a fresh authorization binding the exact final clean
commit. Expiry before that start changes the disposition to blocked and requires a new
immutable metadata/bundle/plan cycle.

# T07 Gate L0 implementation ledger

Status: **assembly complete; lambda-host-selected-design-only; L1/L2/L4
unauthorized; L3 requirements only**

Source contract: `/Users/joseph/Downloads/T07_GATE_L0_LAMBDA_LINUX_HOST_PIVOT.md`,
14,378 bytes, SHA-256
`d630b569864a3a1125cd62fb92ad67b023faa2195bdc529829aafcb8dfa12efd`.

Baseline: clean parent `phase-1/sira-smoke` commit
`0ce094778f979e303794bbfe01acc93829a7ff1d`; work branch
`phase-1/sira-smoke-lambda`.

## Definition-of-done mapping

| ID | Required outcome | Status | Evidence |
|---|---|---|---|
| T07-L0-01 | Preserve child-branch ancestry and all prior local-runtime rejection evidence. | met | Baseline `0ce0947...` is an ancestor; the child branch is exact; historical Gate A/B1/B1.5/B1.6/B1.7 and superseded Docker/Colima packet diffs are empty. |
| T07-L0-02 | Preserve the locked EXP-0001 scientific contract byte-for-byte. | met | Protocol/config/profile/reactive/simulative hashes remain `5bdf3f...`, `f05767...`, `ab276b...`, `7ca194...`, `68f5f4...`; final gate rechecks them. |
| T07-L0-03 | Perform none of the prohibited account, secret, cloud, SSH, payload, runtime, browser, model, SiRA, or authorization actions. | met | Only local reads, tests, hashing and small official public metadata reads occurred; no secret or account endpoint was accessed. |
| T07-L0-04 | Record exact authoritative paths and terminal local-host rationale. | met | `T07_GATE_L0_LAMBDA_HOST_DECISION.md` records repository inputs and the B1.7 terminal rationale without rewriting prior evidence. |
| T07-L0-05 | Select design-only Lambda x86_64 ephemeral host with no persistent filesystem. | met | D-020, project state, active plan and decision packet align; all execution/cloud permissions remain false. |
| T07-L0-06 | Source-bind current official API/image/pricing/billing/Docker/qualification-image facts without account/payload access. | met | `public-source-observations.json` binds OpenAPI 1.10.0, pricing observation, image family, billing and exact BusyBox metadata; account/payload booleans are false. |
| T07-L0-07 | Create separately authorizable L1 GET-only plan with exact endpoint/call/wall/output/retry/secret/mutation/storage caps. | met | Plan ID `PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V1`, run ID `RUN-T07-L1-LAMBDA-INVENTORY-0001`, committed unauthorized; packet contains exact arrays/caps. |
| T07-L0-08 | Strictly parse/redact account inventory and retain only bounded hashable evidence. | met | Duplicate/nonstandard/deep JSON, DTO drift, secret canary, response/output cap, and redaction tests pass; firewall free text and instance IPs are omitted. |
| T07-L0-09 | Select cheapest qualifying x86_64 tuple deterministically or stop without escalation. | met | Typed selector tests price/stable ties, CPU/one-GPU allowance, multi-GPU/price/resource/architecture/region/firewall/duplicate stops. |
| T07-L0-10 | Compute exact selected one-hour list-price cap under USD 2.00 aggregate ceiling. | met | Integer-cent cost primitive and rounding/cross-link tests; L2 remains non-account-bound until L1. |
| T07-L0-11 | Bind account/workspace/type/region/image/key/firewall/instance identities without prohibited material. | met | Typed DTOs, domain-separated hashes, exact bind validator and success/incident evidence relations are tested. |
| T07-L0-12 | Enforce one-instance no-filesystem launch body without invented account values. | met | Network-inert renderer requires exact selected identities, empty filesystem arrays, one name/tag set, no quantity/user data. No L2 plan exists. |
| T07-L0-13 | Guarantee future post-launch evidence/termination graph by immutable ID, including ambiguous launch and billing incidents. | met | Lifecycle contract, success schema, incident schema and semantic validators cover pre-POST deadline, unique tagged recovery, exact termination target and open incident truth. |
| T07-L0-14 | Pin minimal x86_64 image and numeric containment/transfer/evidence/call/wall/cleanup caps. | met | BusyBox amd64 manifest/config/layer/source locks and all provider/API/SSH/Docker/raw-output/storage caps are recorded. |
| T07-L0-15 | Preserve private PID/cgroup/IPC, no-network, bounded immutable lifecycle and zero-residue requirements. | met | Revised 1,384-byte fixture self-checks applets in the same container; schemas require daemon-side top/log evidence, KILL escalation and zero residue. Kernel proof remains a future L2 obligation. |
| T07-L0-16 | Create only an unauthorized non-account-bound L2 packet after L1. | met | L2 has no plan/hash/auth block; archived L1 evidence, account facts, SSH host trust and fresh authority are explicit blockers. |
| T07-L0-17 | Create L3 requirements-only x86_64 B2b successor. | met | `T07_GATE_L3_B2B_REQUIREMENTS.md` preserves Playwright/SiRA/routing/frozen/probe/provenance boundaries and has no executable plan. |
| T07-L0-18 | Document L4 fresh-authorization live-pair boundary. | met | Decision/readiness/L3 retain exact order/model/science/evidence/termination requirements; no live authority exists. |
| T07-L0-19 | Create/register all inventory, success and incident schemas with positive/adversarial tests. | met | Three `t07-lambda-*.schema.json` files are registered in validation and schema tests; semantic cross-link tests cover success, partial failure and open billing. |
| T07-L0-20 | Update active plan, decision log, project state, storage/readiness records and notebook without claiming a result. | met | D-020 and all active control/public planes state design-only/unauthorized and preserve historical evidence. |
| T07-L0-21 | End `lambda-host-selected-design-only`, L1/L2/L4 unauthorized, L3 requirements-only, all execution/cloud permissions false. | met | Typed project-state parser and Phase 1 closeout tests enforce the terminal state. |
| T07-L0-22 | Run focused gates, repository validation, format/lint/typing and portable-Quarto full gate. | met | Focused Lambda/schema/state suite: 65 passed. Post-review `make check` with portable Quarto 1.9.38: 494 passed; lock, sync, format, Ruff, mypy, repository validation, notebook render and site validation passed. |
| T07-L0-23 | Obtain independent spec-conformance review, repair findings, and rerun post-review gate. | met | `/root/l0_spec_review` returned a clean rereview after deadline, concrete archive, provider pacing, child-secret-environment and pacing-truth repairs; the full post-review gate passed. |
| T07-L0-24 | Commit on the child branch and leave a clean worktree. | met | This ledger is part of the final child-branch commit; its exact non-self-referential SHA and empty porcelain proof are reported in the handoff. |

## Final gate evidence

- Focused suite: 65 passed across `tests/test_lambda_cloud.py`,
  `tests/test_lambda_inventory.py`, `tests/test_harness_schemas.py`, and
  `tests/test_phase1_closeout.py`.
- Static/contract gates: formatter, Ruff, mypy, repository validation, strict JSON,
  hash/byte checks and `git diff --check` passed.
- Full gate: 494 tests plus portable Quarto 1.9.38 notebook render/site validation
  passed after the clean independent rereview.
- Independent review: `/root/l0_spec_review` returned **clean verdict; no remaining
  findings** after two repair/rereview loops.
- Locked scientific hashes, historical evidence diff and branch ancestry were
  reverified; the handoff reports final commit and clean-worktree proof.

## Boundary

Gate L0 performed repository design only. Gate L1, L2, L3 execution, L4, the pilot,
paid compute, cloud mutation, provider/model API calls, browser actions and both SiRA
conditions remain unauthorized. A future L2 plan cannot exist until L1 has separately
authorized, archived and reviewed evidence and the SSH server-host-key blocker is
resolved.

# T07 Gate L2.3 decision binding

Status: **ready-for-manual-console-qualification-authorization; unauthorized**

Date: 2026-08-11

## Decision

Gate L2.3 validated the user's private manual-console decision, resolved its private
resource bindings from sealed evidence, sealed the result locally and to the approved
external archive, and rendered one executable but unauthorized manual plan. The
terminal decision is:

```text
ready-for-manual-console-qualification-authorization
```

This is authorization readiness, not execution authority. The plan keeps
`authorized`, `cloud_mutation_allowed`, `paid_compute_allowed`, and
`prototype_execution_allowed` false. Gate L2M has not started.

## Verified starting state

- Branch: `phase-1/sira-smoke-lambda`.
- Required clean starting commit:
  `b71cbbc29f59da600d57b7f0ad28d14572b5fc62`.
- Reviewed Gate L2.2 implementation ancestor:
  `82670a862e73ae1404fecaec775232445fddcdd8`.
- Qualification manifest:
  `containers/sira-smoke/lambda/manual-console/manifest.json`, 1,510 bytes,
  SHA-256
  `dc9824649f97fab6cfd105b5fc0d0c6c1c5ff513fa25f70e0d517afa623cc261`.
- Every manifest member and every sealed Gate L1, L1A, L1.3 and L2.0 binding passed
  its repository-owned verifier before the private decision was opened.
- The most recent sealed account inventory still records zero running instances. It
  is historical evidence only; the future supervisor must obtain a fresh account-wide
  zero-instance observation before any mutation.
- The approved APFS archive volume was freshly observed mounted, unlocked and
  writable with volume UUID `8478609D-FA37-4ED5-875D-47AE912B9151` and
  physical-store UUID `7904A6F1-F483-4ED7-9E34-BFECAB31C63E`. Execution must
  revalidate it through held no-follow descriptors and may not fall back internally.
- No real credential or account request was needed or used.

The exact governing repository paths read were:

- `AGENTS.md`, `docs/PLANS.md`, `docs/PROJECT_STATE.yaml`,
  `docs/STORAGE_POLICY.md`, `docs/REPRODUCIBILITY.md`, `docs/COMPUTE_POLICY.md`,
  `docs/exec-plans/active/PHASE_1_ARTIFACT_EXECUTION.md` and
  `docs/readiness/PHASE_1_SMOKE_READINESS.md`;
- `docs/harness/T07_GATE_L0_LAMBDA_HOST_DECISION.md`,
  `docs/harness/T07_GATE_L0_IMPLEMENTATION_LEDGER.md`,
  `docs/harness/T07_GATE_L1_READONLY_INVENTORY_AUTHORIZATION_PACKET.md`,
  `docs/harness/T07_GATE_L1_1_REQUEST_LEDGER_REPAIR.md`,
  `docs/harness/T07_GATE_L1_1_IMPLEMENTATION_LEDGER.md`,
  `docs/harness/T07_GATE_L1_2_AUDIT_SCHEMA_ADJUDICATION.md`,
  `docs/harness/T07_GATE_L1_2_IMPLEMENTATION_LEDGER.md`,
  `docs/harness/T07_GATE_L1_V3_AUTHORIZATION_PACKET.md`,
  `docs/harness/T07_GATE_L1_V4_AUTHORIZATION_PACKET.md`,
  `docs/harness/T07_GATE_L1_3_IMAGE_IDENTITY_ADJUDICATION.md`,
  `docs/harness/T07_GATE_L1_3_IMPLEMENTATION_LEDGER.md`,
  `docs/harness/T07_GATE_L1_4_SSH_KEY_FINGERPRINT_DESIGN.md`,
  `docs/harness/T07_GATE_L1_4_IMPLEMENTATION_LEDGER.md` and
  `docs/harness/T07_GATE_L1A_SSH_KEY_AUTHORIZATION_PACKET.md`;
- `docs/harness/T07_GATE_L2_RESOURCE_AND_SECURITY_DECISION_PACKET.md`,
  `docs/harness/T07_GATE_L2_JUPYTER_HOST_KEY_CHECKPOINT.md`,
  `docs/harness/T07_GATE_L2_0_HUMAN_DECISIONS_AND_PLAN.md`,
  `docs/harness/T07_GATE_L2_0_IMPLEMENTATION_LEDGER.md`,
  `docs/harness/T07_GATE_L2_1_LAUNCH_RECOVERY_DESIGN.md`,
  `docs/harness/T07_GATE_L2_1_IMPLEMENTATION_LEDGER.md`,
  `docs/harness/T07_GATE_L2_2_MANUAL_CONSOLE_DESIGN.md`,
  `docs/harness/T07_GATE_L2_2_IMPLEMENTATION_LEDGER.md`,
  `docs/harness/T07_GATE_L2M_USER_RUNBOOK.md`,
  `docs/harness/T07_GATE_L2M_MANUAL_CONSOLE_DECISION_PACKET.md`,
  `docs/harness/T07_GATE_L2M_HOST_QUALIFICATION_AUTHORIZATION_PACKET.md` and
  `docs/harness/T07_GATE_L3_B2B_REQUIREMENTS.md`;
- `schemas/t07-lambda-l2m-human-decision.schema.json`,
  `schemas/t07-lambda-l2m-checkpoint.schema.json`,
  `schemas/t07-lambda-l2m-observer-journal.schema.json`,
  `schemas/t07-lambda-l2m-host-evidence.schema.json`,
  `src/giclab/harness/lambda_l2m_checkpoints.py`,
  `src/giclab/harness/lambda_l2m_observer.py`, the files under
  `containers/sira-smoke/lambda/manual-console/`, and their `tests/test_lambda_l2m_*`
  tests; and
- the ignored/sealed evidence plus the exact EXP-0001 protocol, config, smoke profile
  and two condition plans named below.

## Private decision adjudication

The decision source was opened through a no-follow hierarchy and was a current-user
owned, single-link regular file at mode `0600`. Its 1,505 source bytes have SHA-256
`1b603e4bfb1e63b9046bb5b3d404a083666e7a28437e63a20613d7321063bad4`; its
canonical decision SHA-256 is
`6b7af4f2c567f8c8e66f3d165e8ffbc144028cf3edf45727bb569e254c7bb75f`.
The public decision alias is `l2m-decision-6b7af4f2c567`.

Validation proved, without publishing the private fields:

- one fresh lowercase 64-hex nonce and one globally routable IPv4 `/32`;
- every required approval, workspace/exclusivity/presence attestation and outage-risk
  acknowledgement explicitly true;
- `img-0032`, `lambda-stack-22-04`, `22.4.5-2141`, `gpu_1x_a10`, `us-east-1`,
  `fractal-lambda-codex`, no persistent filesystem, Jupyter-only access and zero SSH;
- exactly USD 2.00 provider cost, 3,600 seconds provider wall and 300 seconds per
  checkpoint; and
- explicit manual global restriction, regional ruleset creation, one launch click,
  instance termination, ruleset deletion and exact global restoration.

No private IPv4, nonce, raw provider ID, public-key fingerprint, private path or
future Jupyter credential appears in this repository record.

## Private resolution and archive proof

The materializer privately resolved the approved image alias, unique sealed SSH-key
match, current global-firewall snapshot, private `/32`, owned-ruleset marker,
checkpoint identities, manual-run identity and archive identity. Only these public
bindings are retained here:

| Binding | Public-safe identity |
|---|---|
| Decision alias | `l2m-decision-6b7af4f2c567` |
| Marker alias | `l2m-marker-dfc9017f4bc5` |
| Archive alias | `l2m-archive-abdfb6a398ac` |
| Decision seal SHA-256 | `2516d9d902c225f3576e7be193a772b27eb208a85fd4ac63b7d9faa3a101eff6` |
| Private parameters SHA-256 | `cfd40a341759d3a52f7c3161d1f28002d8f4945fbdf1cf62e69e2fccfb76f6b6` |
| Private bundle seal SHA-256 | `10f4f1798b11593528088c6ceff47418b6d6c3baa7b9caa3d74c1de1dd314c48` |
| External copy record SHA-256 | `3436784c72bb01bce0e0e6fc0b1c42e08e26cb106d5306a9b50f8c8b8f7b1c2d` |
| External seal SHA-256 | `5b1fea4933b1d42db51925af7ab6112826de26912a707bf36a29962b6fe79f95` |

Source and destination hashes were verified, both sides were fsynced, the external
destination was atomically finalized, the local source was retained, and no internal
fallback occurred. Raw mappings remain only in ignored, mode-restricted evidence.

## Rendered plan

- Plan: `PLAN-T07-GATE-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-V3`.
- Run: `RUN-T07-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-0003`.
- Path:
  `containers/sira-smoke/lambda/manual-console/gate-l2m-host-qualification-plan-v3.json`.
- Bytes: 21,641.
- SHA-256:
  `1931fcacda4194063c0116ff9630d82f3b8f4ec07ff9b0310342335db629f654`.
- Reviewed implementation commit:
  `af54784f02e4675e25cd21925fd3c5d62cd0ed68`.
- Future authorization placeholder:
  `AUTH-T07-GATE-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-V3-PENDING`.
- Latest safe supervisor start:
  `2026-08-12T05:15:19.646016Z`.

After that timestamp, the public metadata freshness/headroom contract cannot be met;
a new metadata record, bundle, plan, review and authorization are required. The plan
must never be edited in place.

## Scientific lock and execution boundary

The locked EXP-0001 protocol, config, smoke profile, reactive plan and simulative plan
retain SHA-256 values `5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c`,
`f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d`,
`ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425`,
`7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018`
and `68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436`.
The plan preserves reactive first, simulative second, pair
`PAIR-EXP0001-SMOKE-0000`, model `gpt-4o-2024-11-20`, directional reproduction,
`interpretation_allowed: false`, pilot unauthorized and training false.

This turn made no Lambda/account/model/public-IP request, accessed no real secret,
performed no cloud mutation or paid compute, and used no SSH, Jupyter, browser,
container, SiRA or scientific execution.

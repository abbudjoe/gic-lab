# T07 Gate L1.3 implementation ledger

Status: **complete; Gate L2 blocked and unauthorized**

Branch: `phase-1/sira-smoke-lambda`

Baseline: `42f74481e5a500cacb4973c6b29da4c3470679fe`

Source contract: `/Users/joseph/Downloads/T07_GATE_L1_3_RESOURCE_IDENTITY_AND_L2_SECURITY_DESIGN.md`.

This is an offline adjudication and design gate. It authorizes zero account requests,
cloud mutations, SSH operations, private-key reads, model calls, browser/container/SiRA
execution, paid compute, or scientific execution.

## Definition-of-done ledger

| ID | Obligation | Status | Planned evidence |
|---|---|---|---|
| L13-01 | Prove the exact clean baseline, immutable run-0003 hashes/archive equality, seven completed outcomes, external-volume identity, zero running instances, and scientific locks before editing. | met | Starting command record and immutable regression tests. |
| L13-02 | Pin first-party firewall documentation and OpenAPI 1.10.0 with URL, retrieval time, bytes, SHA-256, and exact supported operations/facts. | met | `public-security-observation-l1-3.json`; source-grounded decision document and source tests. |
| L13-03 | Adjudicate duplicate image identities without exposing raw IDs and preserve run-0003 unchanged. | met | `verifier_key_bug`; sanitized structural adjudication; immutable V3 plan/run hash tests. |
| L13-04 | Implement stable inventory-local aliases, canonical availability aggregation, conflict rejection, and an ignored sealed raw-ID map. | met | Typed projection; 124-alias ignored map/seal; exact held-no-follow repository path, exclusive dirfd writes, and path/symlink/map-tamper tests. |
| L13-05 | Repair typed post-run verification without weakening required-field/type or provenance checks. | met | Authoritative L1.3 consumer revalidates the complete ledger, inventory, extension report, archive, storage, adjudication, and private alias-map semantics while historical V3 files remain frozen. |
| L13-06 | Derive every eligible instance/image/region tuple, fixed top-three ranking, exclusion reasons, and fresh-revalidation requirement. | met | Six qualifying tuples, 23 exact near-miss rows, schema-valid candidate matrix, threshold/order tests. |
| L13-07 | Inspect only local `.pub` files and metadata; compute standard fingerprints without reading private-key bytes. | met | Held-dirfd/O_NOFOLLOW public-key reader, strict SSH wire parser, seven sanitized local key records, metadata-only private-file check, and symlink/TOCTOU/malformed-wire tests. |
| L13-08 | Match account keys only when sealed account public-key evidence permits; otherwise fail closed as evidence-insufficient. | met | All three account keys are `evidence_unavailable`; no recommendation; exact blocker recorded. |
| L13-09 | Produce a source-IP-free global-firewall assessment and enforce the exact strict qualification predicate. | met | Four sanitized rules; strict false; exact user-approved-public-`/32` predicate tests. |
| L13-10 | Encode global replacement snapshot/verify/restore/incident states and reject per-instance-only mitigation. | met | Typed exact private raw-snapshot artifact plus seal with bounded exclusive no-follow writes and fsync/readback evidence; account-wide-zero/dependency/IP preconditions; exact replacement GET; same-instance terminal proof before restore; missing/tamper/order/restoration/incident tests; and the missing regional-ruleset blocker. |
| L13-11 | Keep independent-channel host-key trust preferred and TOFU/no-launch explicitly user-gated. | met | Host-key decision record and user-gate tests. |
| L13-12 | Produce a non-executable, account-bound human decision packet with every unresolved Gate L2 choice and authorization false. | met | `T07_GATE_L2_RESOURCE_AND_SECURITY_DECISION_PACKET.md`; terminal state `inventory-evidence-insufficient`. |
| L13-13 | Add all four required schemas and the complete deterministic local regression suite. | met | Meta-schema, independent threshold/ranking boundaries, real sealed-evidence consumer, alias/key/firewall adversarial tests, full Lambda/archive, privacy, immutable-evidence/scientific hashes, and no-network tests. |
| L13-14 | Update the active plan, decision log, readiness, project state, Lambda README, prior L2 packet, and sanitized notebook note. | met | Typed project state plus D-023 and sanitized public/governance updates. |
| L13-15 | Pass formatting, Ruff, strict mypy, repository validation, portable-Quarto `make check`, independent spec/privacy/cloud-safety review, repairs, and post-review full gate. | met | Current focused and combined gates pass; independent rereview is clean; final post-review `make check` result recorded below. |
| L13-16 | Commit on the required branch, leave a clean tree, preserve all prohibited boundaries, and stop before Gate L2 authorization. | met | Final branch commit and clean-status proof are supplied in the handoff; authorization/mutation counters remain zero. |

## Locked scientific byte identities

- `protocol.yaml`: `5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c`
- `config.yaml`: `f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d`
- `run-plans/smoke.yaml`: `ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425`
- reactive condition: `7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018`
- simulative condition: `68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436`

The regression suite checks these exact bytes; the final validation also runs
`git diff --exit-code -- experiments/EXP-0001-sira-simulative-vs-reactive` against
the required baseline.

## Evidence identities and validation

- post-run adjudication: 23,043 B, SHA-256
  `95b08f6e9345aa09ba4b81dcb6b70484ca0a4d2a964cc553f2a3ae4fe96ee782`;
- image-identity schema SHA-256:
  `554f5ef4e456f75339ccf20eb2f44e9e0e7db7e6fefb0fbb4b41cefe2ad3d2ea`;
- candidate-matrix schema SHA-256:
  `d7d6e34e4f0ed15e9edc7083002527eb38f5694d268102a6d29a0d47f53b674f`;
- firewall-assessment schema SHA-256:
  `accb3017777429de71861018222190f17a7338d53d3515e624001a48393d5095`;
- SSH-key-match schema SHA-256:
  `44a09e82b14bca6cf0609c2942402141b41850799123e0efd32156609dea6bac`;
- focused L1.3 suite: 43 passed;
- combined Lambda/archive/request-ledger/storage/schema/closeout suite: 262 passed;
- sensitive-value scan: 135 private values compared with 22 candidate files, zero hits;
- repository validation, Ruff, strict mypy, `git diff --check`, frozen-science diff,
  and the accepted portable-Quarto 16-page site gate: passed;
- independent spec-conformance, privacy, and cloud-safety rereview: clean, no
  remaining findings;
- final post-review `make check`: Ruff and strict mypy passed, 648 tests passed,
  repository and 16-page site validation passed.

## Assembly mapping

- Image identity and post-run evidence: L13-01, L13-03 through L13-05.
- Resource and security decisions: L13-02, L13-06 through L13-12.
- Repository contracts and handoff: L13-13 through L13-16.

No later gate may begin while this ledger is in progress. The only permitted terminal
decision states are `ready-for-human-L2-decisions` or
`inventory-evidence-insufficient`; neither authorizes Gate L2.

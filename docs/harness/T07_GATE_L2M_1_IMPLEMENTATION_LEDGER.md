# T07 Gate L2M.1 implementation ledger

Assembly status: **complete**

Source contract: user-supplied `T07_GATE_L2M_1_FIREWALL_BASELINE_REPAIR.md`.

This workstream is offline. Authenticated account requests, cloud/console mutation,
paid compute, SSH, Jupyter, browser, container, model, SiRA, and scientific execution
are all prohibited.

| ID | Definition of done | Status | Evidence |
|---|---|---|---|
| L2M1-01 | Verify the exact clean starting commit, V3 plan/journal hashes, burned run state, absence of mutation/final observer archive, prior seals, qualification bundle, and five locked scientific hashes. | met | Read-only pre-edit checks at `a8fc2f87a7e84058319c1e245d9ec2dedbac2e5d`; no repository write preceded them. |
| L2M1-02 | Pin the current first-party GET/PATCH global-firewall contract with exact source identity and field rules. | met | OpenAPI 3.1.0/API 1.10.0, 240,288 bytes, SHA-256 `320f4877924984f060b179e86595ed58918a1d0696b60b99cae548ec164934f4`; requiredness, types, nullability, limits, GET, and PATCH captured in the public extraction record. |
| L2M1-03 | Preserve and privately adjudicate observation 0006 without exposing a sensitive scalar. | met | 782-byte regular file, SHA-256 `7168f04f6ad961db10fde3431daa59052f3fc4539128b1bbc2c510e66d37ca25`; classified `incomplete_or_transformed_baseline`. |
| L2M1-04 | If retained evidence is not lossless, create a fresh separately authorizable one-GET capture plan with raw private retention, ledger, sealing, and no mutation. | met | `PLAN-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1`; run `RUN-T07-L2M-FIREWALL-BASELINE-CAPTURE-0001`; 6,311-byte plan SHA-256 `bd61aed7ed1da74ad39ed24c56145d9e816e7ab9b2063f2c962e1cfb79d8a63b`; unauthorized; no V4 manual plan exists. |
| L2M1-05 | Define description-aware, multiplicity-preserving canonicalization and exact PATCH-payload validation for a future complete baseline. | met | Versioned strict canonicalizer, exact restoration builder, private baseline/restoration schemas, semantically validated public report, strict CIDR evidence boundary, duplicate-key rejection, and local adversarial fixtures. |
| L2M1-06 | Make old lossy baselines fail closed in the manual observer/supervisor; preserve V3 and run 0003. | met | Observer now delegates complete rule semantics to the repaired canonicalizer and separately binds ruleset ID/name; V3 plan/journal/observation hashes remain unchanged and its old observer hash fails closed before credential access. |
| L2M1-07 | Seal the stopped run-0003 incident bundle locally and to the approved APFS archive without altering historical bytes. | met | Incident alias `l2m-incident-81cff71b09e0`; local seal `552f5d57dbb232c09cdffceb9bb2c337f6995994a0dec564be7f90022e2ba15c`, copy record `ac867c4fac4bb51beb66e5247863cb9c00326e7b6186e5718e5f51957f4a5a77`, external seal `283b992203ccbe85491a3ef853b2741a3e183b70d19a8db729db7db5492f98b1`; destination hashes verified, source retained, original hashes unchanged. |
| L2M1-08 | Update all required governance, readiness, packet, runbook, Gate L3, and sanitized notebook surfaces. | met | Active plan, decision log, project state/policy, readiness, packets, runbook, READMEs, Gate L3 requirements, and weekly notebook now expose the blocked historical V3 and one-GET capture boundary. |
| L2M1-09 | Pass focused tests, Lambda regressions, schema/repository validation, privacy scans, Ruff, strict mypy, and portable-Quarto `make check`. | met | Focused firewall/observer/project-state suite, full L2M suite, Lambda inventory/archive/firewall suite, repository validation, Ruff, strict mypy, and sensitive-value/path scans passed. Both the pre-review and post-review offline portable-Quarto full gates passed with 1,048 tests, repository validation, all 16 notebook pages rendered, and site validation. |
| L2M1-10 | Obtain clean independent spec/privacy/cloud-safety/evidence/restoration review, repair findings, rerun full gate, commit, and leave a clean tree. | met | Independent rereview at clean commit `c5c385ebf0da3aaa1091f53c6798f4eab3834718` found no P0/P1/P2 findings after repairs. The post-review full gate passed; this ledger is the sole final assembly-commit change, after which branch, hashes, ancestry, and clean-tree state are reverified. |

No checklist item authorizes the capture request itself or any manual-console action.

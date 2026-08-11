# T07 bounded smoke implementation ledger

Status: **review repairs implemented; independent rereview pending; plan unauthorized**

Baseline/fork: `397a391b736528dd1049023d629100193e823c49`

Reviewed implementation commit: `8ce3629e3ccf3a89ba836df7c9c887fbb06dbdbf`

Plan: `PLAN-T07-BOUNDED-SIRA-SMOKE-V1`, 48,108 bytes, SHA-256
`3e087ce38c272f81e4f46567c77cfe61fa36198316900e5710e817b3e5e4b1a6`.

## Definition-of-done map

| ID | Contract obligation | Evidence | Status |
|---|---|---|---|
| T07-BS-01 | Preserve exact branch/fork/tag topology and historical high-assurance evidence. | Starting Git checks; bounded child only; no topology rewrite. | met |
| T07-BS-02 | Preserve EXP-0001/profile/conditions byte-for-byte, reactive first, simulative second, and prohibit interpretation/pilot/training. | Five locked hashes in plan/validator and focused regressions. | met |
| T07-BS-03 | Create fresh bounded plan/host/condition identities without reusing burned gates. | Plan identity/uniqueness validation. | met |
| T07-BS-04 | Bind exact SiRA commit/tree/lock/patch, Python, uv wheel, amd64 Playwright image/browser, and final image identity. | Containerfile/bootstrap/artifact bindings and public metadata records. | met |
| T07-BS-05 | Route the immutable model through every SiRA role with no fallback or implicit retry. | Gate A adapter/routing plus bounded command/model tests and hashes. | met |
| T07-BS-06 | Enforce exact API/token/call/action/attempt/wall/output/cloud/transfer/disk/observer limits. | Typed budgets, shared work+cleanup meter, tmpfs/copy-out, disk-delta checks, pair reconciliation, overrun tests. | met |
| T07-BS-07 | Use bounded container lifecycle and prove browser/container cleanup before conditions. | Four hardened create templates, no-network fixture, stop→kill→inspect→remove/residue tests. | met |
| T07-BS-08 | Keep real secrets out of planning and design file-only workload injection with forbidden fallback. | Entrypoint/supervisor checks and canary negative scans. | met |
| T07-BS-09 | Capture reconstructable success and failure evidence, accounting, commands, identities, and cleanup in a bounded manifest. | Evidence schema/builder, failure archive, credential-shaped rejection, archive/pair records. | met |
| T07-BS-10 | Revalidate Lambda resources and temporary security before launch, bind one instance, and verify termination/security restoration. | Executable fsync-backed 13-GET observer in five ordered phases and fake transports. | met |
| T07-BS-11 | Bind APFS/UTDM identity/floors, one-way verified archive, source retention, and no fallback. | Held-descriptor archive implementation and storage-guard tests. | met |
| T07-BS-12 | Record 12 blockers, seven post-launch stops, seven deferred limitations, allowed claims, and one-pair expiry. | Governance, plan, schema, and exact validator. | met |
| T07-BS-13 | Produce required schemas, executable bundle/control plane, governance, plan, runbook, packet, and repository state updates. | Required paths plus repository validation. | met |
| T07-BS-14 | Run focused/shared tests, schema/repository/privacy checks, Ruff, strict mypy, and portable full gate. | Validation record below. | met |
| T07-BS-15 | Independent scientific-scope/privacy/spend/cleanup review, repairs, clean rereview, and full post-review gate. | Review and validation records below. | pending |
| T07-BS-16 | Commit the reviewed packet on the bounded branch and leave a clean tree without execution. | Final handoff commit/status. | pending |

## First independent review and repairs

The first independent review returned `bounded-smoke-blocked-material-risk`. Its eight
findings were accepted and repaired architecturally in commit
`8ce3629e3ccf3a89ba836df7c9c887fbb06dbdbf`:

1. Added an executable in-process Lambda observer with a bounded append-only fsync
   ledger, closed failure taxonomy, exact phase/order enforcement, and no replay after
   an uncertain send.
2. Added a separate prelaunch security phase that proves both temporary firewall
   controls before launch.
3. Added bounded, secret-scanned failure packaging, not success-only archival.
4. Replaced contradictory repository authorization with a typed external mode-0600
   single-run overlay/private binding, schemas, renderer, and planned zero-actual
   `CMP-0001` record while leaving repository permissions false.
5. Replaced writable host condition-output mounts with finite tmpfs and immutable-ID
   copy-out before removal.
6. Implemented held-descriptor APFS/UTDM archival with destination reread, SHA-256,
   fsync, atomic finalization, source retention, and no fallback.
7. Unified work and cleanup under one 128-call/33,554,432-byte meter and enforced the
   17,179,869,184-byte runtime disk delta; the uv transfer is exact while Git/image
   wire metering is explicitly retained as a limitation rather than overstated.
8. Reconciled archive capacity and storage floors to a 301,989,888-byte cap including
   control overhead.

Mock/fake tests validate this control plane; they do not claim kernel containment,
actual provider behavior, or scientific results.

## Validation record

Pre-rereview validation after the repair commit:

- focused bounded supervisor/plan/budget/evidence/storage/lifecycle tests: passed;
- Gate A/container and all Lambda inventory/ledger regression tests: passed;
- plan/schema/scientific hash validation and privacy scans: passed;
- `UV_OFFLINE=1 make check-python`: passed; Ruff and strict mypy passed;
- full portable-Quarto pre-rereview gate: 1,087 tests passed; Ruff, strict mypy,
  repository/site validation, and all 16 notebook pages passed/rendered.

Independent rereview and the full portable-Quarto post-review gate are recorded after
they complete.

## Execution boundary

No real secret, account or model endpoint, Lambda mutation, paid compute, SSH,
Jupyter, image pull/build, Docker daemon, Chromium, SiRA condition, or scientific
execution was used. The plan and pending authorization reference are inert until a
fresh current-turn user authorization is materialized against the final clean commit.

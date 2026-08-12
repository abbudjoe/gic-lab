# T07 bounded smoke implementation ledger

Status: **final validation and independent rereview pending; plan unauthorized**

Baseline/fork: `397a391b736528dd1049023d629100193e823c49`

Reviewed implementation commit: `e3c68268ecb02375a7b3f78da0187ce1136f06c0`

Plan: `PLAN-T07-BOUNDED-SIRA-SMOKE-V1`, 55,789 bytes, SHA-256
`0128e632e0a3a01f7ee0b9014396fed5782c8afa98459fe9ad4db5cc7db3148f`.

## Definition-of-done map

| ID | Contract obligation | Evidence | Status |
|---|---|---|---|
| T07-BS-01 | Preserve exact branch/fork/tag topology and historical high-assurance evidence. | Starting Git checks; bounded child only; no topology rewrite. | met |
| T07-BS-02 | Preserve EXP-0001/profile/conditions byte-for-byte, reactive first, simulative second, and prohibit interpretation/pilot/training. | Five locked hashes in plan/validator and focused regressions. | met |
| T07-BS-03 | Create fresh bounded plan/host/condition identities without reusing burned gates. | Plan identity/uniqueness validation. | met |
| T07-BS-04 | Bind exact SiRA commit/tree/lock/patch, Python, uv wheel, amd64 Playwright image/browser, and final image identity. | Containerfile/bootstrap/artifact bindings and public metadata records. | met |
| T07-BS-05 | Route the immutable model through every SiRA role with no fallback or implicit retry. | Gate A adapter/routing plus bounded command/model tests and hashes; every completion requests and proves the standard `default` service tier. | met |
| T07-BS-06 | Enforce exact API/token/call/action/attempt/wall/output/cloud/transfer/disk/observer limits. | Typed budgets, shared work+cleanup meter, tmpfs/copy-out, disk-delta checks, pair reconciliation, overrun tests. | met |
| T07-BS-07 | Use bounded container lifecycle and prove browser/container cleanup before conditions. | Four hardened create templates; opt-in readiness/release barrier; required live/nonempty process evidence; stop→kill→inspect→remove/residue tests. | met |
| T07-BS-08 | Keep real secrets out of planning and design file-only workload injection with forbidden fallback. | Entrypoint/supervisor checks, schema-key filtering, value/encoding/hash-derivative scans, opaque canary negatives, cleanup proof, and mandatory rotation on unresolved credential exposure. | met |
| T07-BS-09 | Capture reconstructable success and failure evidence, accounting, commands, identities, and cleanup in a bounded manifest. | Canonical-root evidence builder/failure archive plus closed failure codes, command receipts, decoded ZIP/member/manifest/hash, pair-diff, regulation/event, budget, and compute-use verification. | met |
| T07-BS-10 | Revalidate Lambda resources and temporary security before launch, bind one instance, and verify termination/security restoration. | Executable fsync-backed 13-GET observer in five ordered phases, no-replay state, and expiry-tolerant cleanup-only continuation under fake transports. | met |
| T07-BS-11 | Bind APFS/UTDM identity/floors, one-way verified archive, source retention, and no fallback. | Held-descriptor archive implementation, at most 125 payload plus three seal files, exact upload-artifact retention, and storage-guard tests. | met |
| T07-BS-12 | Record 12 blockers, seven post-launch stops, seven deferred limitations, allowed claims, and one-pair expiry. | Governance, plan, schema, and exact validator. | met |
| T07-BS-13 | Produce required schemas, executable bundle/control plane, governance, plan, runbook, packet, and repository state updates. | Required paths plus repository validation. | met |
| T07-BS-14 | Run focused/shared tests, schema/repository/privacy checks, Ruff, strict mypy, and portable full gate. | Validation record below. | in-progress |
| T07-BS-15 | Independent scientific-scope/privacy/spend/cleanup review, repairs, clean rereview, and full post-review gate. | Review and validation records below. | in-progress |
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

## Second independent review and repairs

The first rereview of the candidate packet also returned
`bounded-smoke-blocked-material-risk`. All seven findings were accepted. Commit
`4c15b8aaf61a260dbdc0063538a2d8500ac95a45` repairs them at their control-plane
boundaries:

1. Replaced macOS `/usr/bin/python3` in all exact local arrays with the repository's
   pinned `.venv/bin/python` and added a real import/CLI smoke.
2. Replaced archive-name-only admission with decoded ZIP path/member/manifest/hash,
   identity, pair, and secret verification before local sealing.
3. Replaced terminal burn-on-failure with typed cleanup-only continuation that cannot
   replay attempted request ordinals and permits termination/restoration observations
   after expiry.
4. Replaced retained raw Lambda bodies with in-memory validation followed by
   schema-declared projection and credential-key filtering.
5. Added source-linked per-condition regulation decisions, normalized pair events,
   the exact command-difference record, and runtime compute-use closeout requiring
   later `CMP-0001` reconciliation.
6. Made the 128-file archive limit exact: at most 125 copied payload files plus three
   seal files.
7. Added an opt-in entrypoint readiness/release barrier and now require a live running
   inspect plus a nonempty process snapshot; file existence alone cannot satisfy the
   cleanup record.

## Subsequent independent reviews and repairs

The next review cycles found five related evidence-boundary gaps. They were repaired
at the control-plane boundary in commits `889da3c3efb37e4f8980fbfaf1089bc58e7b8197`,
`0715a2f1a5d52bd90a2d20792e30ac8f906ade81`,
`6c9d81c364adde12b655c9714e94753f7a36e911`,
`f8e93832e2089e171bfc5d26e17312b5c050d02c`, and
`e3c68268ecb02375a7b3f78da0187ce1136f06c0`:

1. The local verifier now constructs one deterministic tracked-only 36-member USTAR
   archive: one manifest, the plan, and the 34 bound implementation artifacts. The
   reviewed bootstrap is uploaded separately and is not counted as an archive member.
   Untracked, ignored, private, environment, Git, artifact, and secret paths fail
   admission. The local release binds the archive, manifest, bootstrap, observer
   evidence, authorization, and private binding before upload.
2. The standalone remote bootstrap verifies its own identity, atomically claims and
   fsyncs the fixed canonical output root before any fallible authority, bundle,
   contract, plan, release, or secret check, and burns that one-shot identity on every
   terminal pre-secret failure. It verifies the exact archive before importing any
   uploaded repository code.
3. Failure evidence uses closed stage/code enums and bounded command receipts rather
   than arbitrary exception text. Tree traversal counts every entry against the 4,096
   limit, reads are captured once, writes tolerate short writes, downloads are
   hash-checked, and the sealed archive includes the exact upload archive and
   standalone bootstrap needed to reconstruct the attempt.
4. Success and failure capture scan the supplied credential value and its raw, hex,
   Base64, URL-safe Base64, and SHA-256 derivatives. Detected credential material or
   incomplete secret cleanup makes manual credential rotation mandatory and leaves
   security closeout unresolved; schema and verifier invariants enforce that result.
5. Every OpenAI Chat Completions request now explicitly uses `service_tier="default"`
   and every reconciled response must report the same tier. The evidence records the
   requested tier separately from observed response tiers, so a pre-response failure
   cannot falsely claim standard-tier service. The policy is pinned to the retained
   first-party API-reference hash and tested across all SiRA completion paths.

The final review also exposed false-positive secret-hygiene identifiers in the
bootstrap regression surface. Commit
`e3c68268ecb02375a7b3f78da0187ce1136f06c0` renamed only those local identifiers;
the credential detection contract and tests are unchanged. Repository validation now
accepts that surface.

## Validation record

Current pre-rereview validation after the second repair commit and regenerated plan:

- focused bounded supervisor/plan/budget/evidence/storage/lifecycle tests: passed;
- Gate A/container and all Lambda inventory/ledger regression tests: passed;
- plan/schema/scientific hash validation and repository validation: passed;
- full Python regression suite, excluding only the deliberately stale committed-plan
  assertion before regeneration: passed; the regenerated committed-plan test then
  passed;
- repository-wide Ruff and strict mypy (57 source files): passed.
- pre-rereview portable-Quarto 1.9.38 `make check`: 1,092 tests passed;
  repository validation, 16-page render, and site validation passed. Quarto emitted
  its known non-fatal external-output-path warning.

Independent rereview, any resulting repair loop, and the final post-review gate remain
in progress.

## Execution boundary

No real secret, account or model endpoint, Lambda mutation, paid compute, SSH,
Jupyter, image pull/build, Docker daemon, Chromium, SiRA condition, or scientific
execution was used. The plan and pending authorization reference are inert until a
fresh current-turn user authorization is materialized against the final clean commit.

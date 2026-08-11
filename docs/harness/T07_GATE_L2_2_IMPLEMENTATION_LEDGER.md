# T07 Gate L2.2 implementation ledger

Status: **validated; independent rereview clean — blocked-human-image-selection**

Date: 2026-08-10

Source contract:
the user-supplied `T07_GATE_L2_2_MANUAL_CONSOLE_JUPYTER_DESIGN.md` contract.

This assembly ledger maps the offline Gate L2.2 contract to implementation and
evidence. Nothing in this work authorizes an account request, console mutation, paid
compute, SSH, Jupyter, a container, a browser, a model call, SiRA, or scientific
execution.

| ID | Definition-of-done item | Status | Observed evidence |
|---|---|---|---|
| L22-01 | Verify exact branch, clean starting commit, sealed evidence, storage identity, scientific hashes, local-runtime rejection, and zero sealed running instances before editing. | met | Read-only Git, SHA-256, file-mode, disk identity, and structural inventory checks. |
| L22-02 | Pin current first-party Lambda console, image, Cloud IDE, firewall, termination, billing, read-only API, and public BusyBox OCI contracts with exact identities. | met | Bounded public reads only; source-observation record with URLs, versions, bytes, retrieval time, and SHA-256. |
| L22-03 | Privately enumerate and rank `lambda-stack-22-04` image candidates without exposing raw IDs; do not claim type-specific compatibility absent a source contract. | met | Sealed inventory projection proves opaque aliases, versions, architecture, region, and deterministic ranking only. `gpu_1x_a10` offeredness remains blocked pending the required pre-mutation console check. |
| L22-04 | Reject GPU Base as lacking a documented Jupyter guarantee and require a new human image decision rather than silently changing it. | met | First-party image table plus private-decision binding and terminal decision. |
| L22-05 | Define the complete private manual-console decision schema and deliberately non-authorizing template without creating the user file. | met | Draft 2020-12 schema, invalid public template, exact private path and permissions contract; no user file created. |
| L22-06 | Define a >=160-bit private ruleset ownership marker and exact zero/one/multiple-match semantics. | met | Typed marker/ruleset/instance classifiers require exact sole ruleset attachment and retain the image-selection evidence hash. |
| L22-07 | Define exact strict global-firewall replacement, verification, preservation-on-incident, and restoration semantics with no added Jupyter port. | met | Private semantic hash/restoration verifier plus typed cleanup-only strict-firewall incident tests; later read-only recovery requires a fresh reviewed authorization. |
| L22-08 | Implement single-use mode-0600 no-follow nonce-bound private checkpoint validation for all required user actions. | met | Twelve exact per-type schema conditions, <=300-second windows, repository-bound schema identity, held descriptor, exclusive 262,144-byte fsync consumption ledger, replay rejection, and typed partial-write/fsync uncertainty that can advance cleanup only while marking evidence incomplete. |
| L22-09 | Implement a read-only observer surface with exact GET allowlist and finite call/time/output/journal caps and no concrete mutation/SSH/browser/Jupyter boundary. | met | Network-inert-on-import in-process GET transport and trusted engine; pre-send phase/call/byte/journal reservations; exact five-response preflight; durable intent/send/terminal events; prelaunch terminal failures and postlaunch cleanup-only incidents; request-ordinal burning; per-engine evidence capabilities; end-to-end deadlines; phase-partitioned 44-call budget; one-second starts; 6,300-second observer wall; raw responses hashed and schema-validated only in memory; exact allowlisted private projections strip Jupyter credentials, URLs, and additive scalar fields; incomplete journal prefixes remain sealable but scientifically ineligible; pre-finalize held-descriptor archive verification. |
| L22-10 | Create a deterministic Jupyter-uploadable qualification bundle with manifest, host facts, runtime inspection, pinned BusyBox fixture, lifecycle driver, and evidence packager. | met | Exact six-member manifest including a public OCI observation; pre-Docker 86,400-second freshness/identity gate; Python 3.10 syntax parse; shell-free arrays; fake success/failure/signal execution; held-descriptor source/archive packaging; bounded streaming process output; 68,157,440-byte worst-case remote retained cap; no Docker run. |
| L22-11 | Require exact host/container/evidence identities, TERM-to-KILL cleanup, zero owned residue, and bounded evidence/archive validation. | met | Success validator cross-checks three inspect states and seven log events; failure archives record cleanup proof/incident and remain ineligible. |
| L22-12 | Define exact user-only console launch, Cloud IDE, qualification, download, termination, ruleset deletion, and global-restoration sequence. | met | Human-factors runbook, cleanup branches, outage-preserved strict-firewall incident with no same-run replay, typed checkpoint/observation transitions, no identifier-bearing screenshots. |
| L22-13 | Derive exact numeric provider/read-only/user-wait/cost/output/evidence/process caps and honest outage residual exposure. | met | Phase and aggregate call caps, 3,600-second/USD 2.00 ceilings, qualification/output/storage caps, and explicit outage residual. |
| L22-14 | Produce the design, decision packet, runbook, and host-qualification disposition for `blocked-human-image-selection`, with no executable plan or authorization block. | met | Required documents exist; plan and authorization block are explicitly absent. |
| L22-15 | Update Lambda README, project state, active Phase 1 plan, decision log, readiness, Gate L3, and sanitized notebook note without rewriting Gate L2.1. | met | All required governance/public surfaces updated; repository validation passed. |
| L22-16 | Preserve all prior sealed evidence, private decisions, plan/run history, and locked EXP-0001 files byte-for-byte. | met | Starting hashes reverified; post-repair Git diff and hash regressions confirm no locked-file change. |
| L22-17 | Pass focused, Lambda-wide, schema, repository, privacy, formatting, Ruff, strict mypy, and portable-Quarto full gates. | met | 133 focused L2.2 tests and all 517 Lambda tests pass; the non-editable installed-package regression passes; secret/sensitive-value negative scans are clean; the portable-Quarto `make check` passes Ruff, strict mypy, all 971 tests, repository/site validation, and the 16-page notebook render. |
| L22-18 | Obtain independent spec/privacy/cloud-safety/human-factors/incident review, repair findings, rereview, and rerun the full post-review gate. | met | Iterative independent review exposed and drove repairs for authority, ownership, evidence, archive-finalization, request-ledger, interrupt-recovery, storage-driver, provenance, offeredness, and cap gaps. Final rereview returned `CLEAN`; the post-review portable-Quarto gate passed Ruff, strict mypy, all 971 tests, repository/site validation, and the 16-page render. |
| L22-19 | Commit the single permitted terminal state on `phase-1/sira-smoke-lambda` and leave the worktree clean. | met | Gate L2.2 implementation commit `82670a862e73ae1404fecaec775232445fddcdd8`; the ledger-closing commit and final clean-status proof complete the handoff. |

## Required terminal boundary

The observed sealed inventory contains x86-64 Lambda Stack 22.04 regional candidates,
but static sources do not prove type-specific launch-wizard offeredness and the
existing private decision selects GPU Base 22.04. The only truthful current target is:

```text
blocked-human-image-selection
```

No executable manual plan or ready-to-copy authorization may be created unless a new
private human decision first approves the image change under a later reviewed gate.

## Independent-review repair record

The first independent review rejected the initial control plane despite passing local
tests. It found: success-only cleanup transitions; assertion-only inspect/log evidence;
suppressed emergency cleanup; a too-short observer wall; process-local checkpoint
replay protection; widened instance ruleset matching and discarded image binding; late
host validation/mandatory buildx; post-hoc subprocess output caps; and incomplete test
and ledger closure.

The repair replaced each primitive rather than weakening a claim: cleanup transitions
are explicit and typed; inspect/log evidence is cross-validated; failure cleanup is
sealed and incident-bearing; late cleanup fits the 3,600-second wall; checkpoint
consumption is durable across readers; the instance must have exactly one attached
owned ruleset and carries the image checkpoint hash; host checks precede Docker;
optional tooling is nullable; subprocess output is killed at its streaming cap; and
fake success/failure/replay/adversarial tests cover the new boundaries.

The first rereview then rejected three remaining control-plane claims. The observer
was only a renderer/classifier, so checkpoints discarded their action details and a
caller could fabricate a transition proof; its 3,600-second wall started before launch
and could not also cover post-provider cleanup; Docker output read on a failed call was
not charged to the aggregate counter. The second repair adds an inert-on-import,
exact-host in-process GET engine with fake-transport tests, retains typed checkpoint
details, accepts only engine-issued proofs derived from provider/archive evidence,
seals and copies evidence through the approved storage guard, partitions a 6,300-second
observer wall around the unchanged 3,600-second provider ceiling, and charges streamed
Docker bytes before every success or failure decision.

The second rereview found that request authority still became final only after send;
preflight success was premature; evidence capabilities and qualification paths were
reusable across engines; the UTDM copier reopened a pathname and trusted recomputed
rather than sealed hashes; phase/request deadlines were declarative; and ordinary
Docker output could consume the cleanup path. The third repair reserves every request
authority and terminal-ledger resource before send, stops the run after every
prelaunch failure and cleanup-only after postlaunch failure, proves the exact five-item preflight, scopes tokens to one engine
and exact run/authorization/ordinal/path binding, retains and reverifies the exact
qualification file, copies through held descriptors only after sealed-source hash
verification, enforces active/provider/cleanup/archive and socket-stage deadlines,
and partitions a 1,048,576-byte emergency-cleanup output reserve inside the unchanged
8,388,608-byte Docker aggregate. New regressions cover pre-send rejection,
post-failure non-replay, cross-engine evidence rejection, post-seal mutation,
held-root path swaps, phase/archive deadlines, and cleanup after ordinary-output
exhaustion.

The full non-editable-package gate then exposed one final hidden path contract: schema
bindings were derived from the installed module's `__file__`, so a wheel-style install
looked under `site-packages` rather than the authorized checkout. The final repair
derives and retains one explicit repository root from each exact schema path, requires
the journal, checkpoint reader, private human-decision capability, endpoint schemas,
and host-evidence schema to share that root, and continues to enforce the exact
repository-relative path and SHA-256 for every schema. The focused L2.2 suite passes
both from source and after an exact `--no-editable` installation; the subsequent full
gate passes all 939 tests.

The current privacy/cloud-safety rereview found four further hidden contracts. Docker
`create` could implicitly pull despite a pre-pull digest check; `BaseException` during
checkpoint or journal append could escape without exact-prefix recovery; the
instance/termination call text implied detail rounds that the allowlist forbids; and
durable provider evidence inherited additive response fields, including documented
Jupyter credentials. The repair adds `--pull=never`, BaseException-safe typed
uncertainty with exact-prefix sealing and copy verification, an engine/schema-aligned
44-GET partition with ten list-only bind and terminal observations, and exact private
projections. Raw responses are bounded, hashed, and schema-validated in memory only;
durable projections independently bind the raw and projected hashes while omitting
Jupyter tokens/URLs and unknown scalar values. Successful receipt integrity and every
incomplete-prefix failure path now have end-to-end local/external sealing regressions.
The resulting full gate passes all 946 tests.

The next rereview exposed four evidence-truthfulness primitives: a twice-observed
zero-instance launch outcome still demanded a nonexistent termination click;
checkpoint windows were not anchored to a trusted current clock; failure-archive
validation reopened a mutable pathname; and ZIP packaging reopened both evidence and
archive paths across race windows. The repair gives zero launch its own direct
terminal proof while requiring every observed post-click row to be terminated under
the sealed zero-baseline/exclusive-window premise, anchors challenge windows and
observations to injected current UTC, validates the exact held archive bytes, and
uses no-follow held directory/member/archive descriptors through atomic finalization.
Adversarial path-swap and old-checkpoint regressions cover those contracts.

The same review found the BusyBox pull lacked an executable current-metadata
prerequisite and its evidence wording overstated what happened. The public OCI record
is now a required manifest member. Before constructing a Docker budget, the driver
requires its exact hash and structure, exact pinned platform/manifest/config/layer
identity, zero account/authenticated/layer-download counts, and age no greater than
86,400 seconds. Host evidence separately records the earlier public-registry
revalidation, the in-qualification repository-binding validation, and zero standalone
registry-metadata requests. An expired record fails before Docker; later
materialization must refresh and independently review all derived identities.

The reviewer also found that required runtime identities were merely nullable schema
fields. Runtime observation now stops before pull unless Docker client/server,
containerd, and runc each yield one nonempty bounded version; only buildx and BuildKit
remain optional. Missing-containerd and missing-runc regressions enforce eligibility.

The final control-plane review identified further interrupt, provenance, containment,
and governance windows. The repair proves `linux/amd64` from the pinned OCI config
blob; refuses direct driver entry and uses an isolated verified bootstrap; resolves an
outcome-unknown Docker create through a unique name, dual labels, immutable-ID
cleanup, and stable-absence proof; reserves ten Docker calls for cleanup; requires
launch-wizard offeredness instead of claiming a static type/image compatibility
matrix; and separates the later Gate L2M qualification host from Gate L4 scientific
execution. Qualification validation is hard-bounded through its durable receipt.
Every checkpoint stage retains typed recovery state; the reader returns a verified
checkpoint through an in-reader consumption callback, and recovery recognizes an
already-consumed engine-issued observation without replay. Deterministic
`BaseException` regressions cover archive validation, validation receipts,
consumption-return, observation-consumption, apply, lifecycle, and receipt windows.

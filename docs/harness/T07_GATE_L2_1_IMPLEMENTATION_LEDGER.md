# T07 Gate L2.1 implementation ledger

Status: **complete — manual-console-launch-required**

Date: 2026-08-10

Source contract:
`/Users/joseph/Downloads/T07_GATE_L2_1_LAUNCH_RECOVERY_AND_SUPERVISOR.md`.

This assembly ledger tracks the single Gate L2.1 workstream. `met` means the offline
contract item has direct local evidence; `partial` means useful fake-tested primitives
exist but do not compose the required live authority; `blocked` means the requirement
cannot truthfully support an executable plan. Nothing in this ledger authorizes an
account request, cloud mutation, paid compute, SSH, container, browser, model, SiRA,
or scientific action.

## Definition-of-done ledger

| ID | Contract item | Status | Observed evidence |
|---|---|---|---|
| L21-01 | Exact branch, starting commit, clean worktree, evidence/scientific hashes, zero sealed running instances, closed local-runtime path | met | Started on `phase-1/sira-smoke-lambda` at clean `1a72670d2c5ee35566b66bcccbbf15e0942e5b1f`; identity/science checks passed before editing. |
| L21-02 | Revalidate existing private human decision without printing private fields | met | Current-user mode-`0600` no-follow regular file, 1,047 bytes, SHA-256 `0b109b0150eec8739e30e86e5f1318b60c818cc3974354c67dc35a4e2dffd4ea`. |
| L21-03 | Pin first-party Lambda OpenAPI identity and relevant schemas | met | OpenAPI 1.10.0, 240,288 bytes, SHA-256 `320f4877924984f060b179e86595ed58918a1d0696b60b99cae548ec164934f4`; canonical extraction hashes are in `public-source-observations-l2-1.json`. |
| L21-04 | Adjudicate provider idempotency and observable ownership semantics | met | No launch idempotency key/header is documented; marker fields are optional/nonunique; image is not observable in `Instance`. |
| L21-05 | Define >=160-bit private single-use ownership marker and exact visible derivations | met | HMAC-SHA-256 domain binding, 32-byte generation/20-byte minimum, exact name/hostname/two-tag renderers, privacy projection, schemas, tests. |
| L21-06 | Require zero full and zero partial marker matches before launch | met | Typed classifier and adversarial local fixtures reject full/partial/conflicting prelaunch observations. |
| L21-07 | Define full ownership conjunction and detail revalidation without invented image visibility | met | Parser/predicate/detail helper and fixtures cover all documented observable fields. |
| L21-08 | Implement append-only fsync launch transaction journal | met | Exclusive-create schema-valid writer with sequence/cap/fsync tests. |
| L21-09 | Enforce exactly one launch send, immutable body, and no replay after possible send | partial | Fake state-machine paths burn the marker and reject resend; no authoritative runner owns every route and exception. |
| L21-10 | Implement bounded list/detail discovery outcomes | partial | Typed classification and fake call helpers exist; wall/spacing/phase subcaps are not integrated into a live loop. |
| L21-11 | Bind exact IDs only after response or discovered-candidate detail revalidation | partial | Single-candidate fake path revalidates; duplicate full matches are not independently revalidated end-to-end. |
| L21-12 | Implement exact-ID termination journaling and terminal proof without blind resend | partial | Fake intent/send and no-replay paths exist; terminal status and provider disappearance remain caller assertions rather than one observed polling loop. |
| L21-13 | Preserve strict firewall and raise high-severity incident while unresolved | partial | Typed incident/state guards exist; mutation, verification, and exact restoration effects are not owned by one runner. |
| L21-14 | Implement one authoritative supervisor through archive finalization | blocked | Public provider/process methods and assertion-style transition methods are not one phase-exact effecting orchestration; post-mutation cleanup is incomplete. |
| L21-15 | Enforce aggregate provider/process/output/wall/cost counters across primary and cleanup | blocked | Process-local `SharedBudget` and separate `FsyncSharedBudget` exist but are not one API shared by primary/watchdog; many documented subcaps are constants only. |
| L21-16 | Route all cloud calls through one in-process HTTPS policy boundary | partial | Draft exact-host boundary exists, but there is no executable runner; D-027 now makes the concrete sender fail before connection creation. |
| L21-17 | Route all local/SSH/container commands through one exact shell-free policy | partial | Draft allowlist exists, but exact arrays/order are not enforced; D-027 makes the concrete subprocess boundary fail before `Popen`. |
| L21-18 | Project sensitive provider/process fields before persistence | partial | Allowlists/canary tests exist; no live end-to-end evidence path proves every exception/output uses them. |
| L21-19 | Enforce complete success/incident evidence eligibility | partial | Predicate and schemas exist, but caller-supplied booleans/hashes are not bound to actual journal/effect objects. |
| L21-20 | Keep archive finalization bound to held no-follow descriptors | met | Historical V1 copy primitive verifies through the staging descriptor after atomic rename; misleading partial V2 generalization was removed. |
| L21-21 | Source-adjudicate and design independent local watchdog | partial | Apple launch-service manuals and local primitives were evaluated; no supported integrated cleanup runner was established, and concrete spawn now fails before pipe/fork. |
| L21-22 | Implement separate watchdog journal, heartbeat, takeover, and mutation exclusion | partial | Fake-tested journal/heartbeat/flock/takeover helpers exist; no live entrypoint wires effects, shared caps, timed waits, or inherited-descriptor closure. |
| L21-23 | Ensure watchdog never launches, SSHes, or mutates unrelated resources | partial | Closed operation allowlist rejects launch/SSH in unit tests; no live authority enforces exact target bodies/IDs. |
| L21-24 | State watchdog and outage limits honestly | met | Design/packet contain the exact residual statement and ordinary/simultaneous/power/network/API/console limits. |
| L21-25 | Create private-decision template/schema without creating user file | met | Deliberately invalid repository template and strict schema exist; packet now says not to materialize it for the retired design. |
| L21-26 | Derive numeric normal/incident phases and provider/process/evidence caps | partial | Exact draft values exist; enforcement is incomplete and sequential 3,600+1,800+900-second arithmetic exceeds the claimed 5,400-second ceiling. |
| L21-27 | Preserve USD 2.00/3,600 s/600 s/one-launch/no-filesystem/zero-science boundaries and incident caveat | met | Values and explicit non-guarantee are documented as non-authorizing design inputs. |
| L21-28 | Preserve prior plans/evidence and byte-identical EXP-0001 files | met | Historical identities remain present/nonreplayable; final hash regression passed. |
| L21-29 | Produce required design/packet/schema/source/test outputs and update governance/public surfaces | met | Every required path exists; no executable plan was added. |
| L21-30 | Create plan only if technically complete; otherwise choose one terminal alternative | met | Chose `manual-console-launch-required`; no V2 plan/path/bytes/hash or authorization block exists. |
| L21-31 | Run focused, Lambda, schema, privacy, Ruff, strict mypy, repository, and portable-Quarto gates | met | Final validation record below. |
| L21-32 | Obtain independent spec/privacy/cloud/incident/exactly-once review, repair, and rerun | met | Independent review identified P0/P1 composition gaps; claims were terminalized, partial V2 archive surface removed, and post-review gates rerun. |
| L21-33 | Commit one permitted terminal decision and leave branch clean | met | This ledger is included in the final clean Gate L2.1 commit; the immutable commit SHA is reported outside the commit. |

## Independent-review adjudication

The reviewer ran the fake-only ownership/supervisor/watchdog/evidence suite and found
that isolated tests pass but do not establish the required authoritative transaction.
The decisive gaps are effect/assertion separation, missing phase-exact mutation
bodies, no cleanup-from-every-failure runner, no integrated independent watchdog,
unshared cross-process limits/lease, incomplete duplicate/terminal polling, forgeable
completion inputs, nonexact process arrays, and no V2 evidence/schema closure.

These findings are architectural. Adding more assertion-level tests would not make the
path executable. The correct contract outcome is the prompt's terminal alternative:

```text
manual-console-launch-required
```

Final rereview found that plan absence alone did not make the concrete HTTPS,
subprocess, and fork entrypoints inviolable. D-027 guards and regressions were added so
all three fail before their first effect while fake policy tests remain available. The
reviewer then returned a clean terminal verdict.

## Validation record

The final exact commands, counts, and outcomes are recorded after the post-review run:

- focused ownership/supervisor/watchdog/evidence/schema/governance suite: 97 passed;
- all Lambda inventory/archive/key/firewall/Gate L2 regression tests: 384 passed;
- schema/repository validation: `giclab.validation all` passed;
- secret/privacy controls: focused canary/redaction tests and all Lambda privacy tests
  passed; tracked assignment-name scan found only the expected public `.env.example`
  and dummy-secret fixture source, without reading any ignored secret file;
- Ruff and strict mypy: passed for the changed surface; the full gate passed all 49
  typed source files;
- post-review `make check` with portable Quarto 1.9.38: lock/sync, format, Ruff,
  strict mypy, 838 tests, repository validation, 16-page render, and site validation
  passed after the terminal-effector guard repair and clean independent rereview.

## Terminal state

No executable plan was created. The V1 and draft V2 plan/run identities are
non-reusable. A future human-operated console launch requires a new reviewed contract,
fresh identities, and a fresh current-turn authorization. Gate L3/L4, paid compute,
cloud mutation, SSH, container, browser, model, SiRA, and scientific execution remain
blocked.

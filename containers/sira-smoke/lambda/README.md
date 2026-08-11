# T07 Lambda host controls

This directory contains the design-only Gate L0 source locks and unauthorized plans.

Gate L2M V3/run 0003 is now blocked historical evidence: it stopped after six
read-only GETs and before mutation, and its transformed global-firewall projection is
not exact restoration authority. The active proposal is the unauthorized one-GET
`manual-console/gate-l2m-firewall-baseline-capture-plan-v1.json`. It retains the raw
response privately, uses the description-aware canonicalizer, and seals one-way to
the approved archive. It authorizes no request or mutation by itself.

- `gate-l1-readonly-inventory-plan.json` is the byte-preserved historical V1 GET-only
  contract. Both V1 authorizations are blocked evidence; run
  `RUN-T07-L1-LAMBDA-INVENTORY-0001` is permanently retired, and the public V1
  execution entry point is disabled.
- `gate-l1-readonly-inventory-plan-v2.json` is the byte-preserved historical V2
  contract:
  plan `PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V2`, run
  `RUN-T07-L1-LAMBDA-INVENTORY-0002`, SHA-256
  `02d83cb6e303242dec9261146488adfa2b2b026605edc48a95e1fe9ec3b9229e`.
  Its authorization and run are blocked historical provenance. The run
  durably observed one HTTP-200 audit response but stopped at `schema_drift`; its raw
  body was not retained, so the additive adjudication is
  `unadjudicated_raw_body_absent`. The run identity is permanently retired.
- `gate-l1-readonly-inventory-plan-v3.json` is the byte-preserved seven-GET
  contract executed successfully under the now-consumed V4 authorization: plan
  `PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V3`, run
  `RUN-T07-L1-LAMBDA-INVENTORY-0003`, SHA-256
  `b5ec82aaa84882a7c3269ebdb695a6c694f891d66d367c05f82eaf9797515331`.
  It removes audit-history and account-LRN retrieval, binds a separate response schema
  for every retained endpoint, accepts only compatible additive keys while retaining
  no unknown values, treats every non-null continuation as a stop, and requires the
  V3 ledger/archive contracts before Gate L2 eligibility. Run 0003 completed all seven
  GETs with HTTP 200/schema-valid outcomes and was sealed to the approved external
  archive. The plan/run are historical and must not be replayed.
- `endpoint-schemas-v3/` contains the seven pinned response contracts. Import and
  fake-transport tests in `lambda_*_v3.py` perform no account request and use no real
  credential.
- `gate-l1a-ssh-key-fingerprint-plan-v1.json` is the fresh, unauthorized one-GET
  fingerprint-recovery design: plan
  `PLAN-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1`, run
  `RUN-T07-L1A-LAMBDA-SSH-KEY-FINGERPRINT-0001`, 12,448 bytes, SHA-256
  `23b29823b8daf94cfb463b275149ed562656c735955a4f449b8703334de531bc`.
  It permits only a future separately authorized in-process
  `GET /api/v1/ssh-keys`, binds the shell-free supervisor, exact transport, fresh
  ledger/root, exact source-loading wrapper, two-phase archive driver, authoritative
  post-ledger finalization disposition, and privacy-separated evidence, and cannot
  imply key selection, SSH, mutation, paid compute, or Gate L2.
- `endpoint-schemas-l1a/` contains the strict response envelope for that future
  request. Its parser/matcher/ledger/executor/archive tests use local fixtures and
  fake transports only.
- `public-source-observations.json` binds the public API and qualification-image
  metadata inspected during Gate L0. No account API or payload was fetched.
- `public-security-observation-l1-3.json` binds the unauthenticated OpenAPI/firewall
  documentation used for the offline image-identity and firewall adjudication.
- `adversarial-containment.sh` is the immutable future Gate L2 fixture source,
  SHA-256
  `09838913b14d23da939225cb89411619e91cb9ee023a2721b5b7c3890ac90aea`.
  It has not run and is not a standalone containment boundary.
- `public-source-observations-l2-0.json` binds the current first-party Lambda
  OpenAPI/docs, local OpenSSH manuals, and official BusyBox OCI metadata used by the
  offline Gate L2.0 design. It records the same-version OpenAPI byte change without
  making an account request or fetching a layer.
- `public-source-observations-l2-1.json` binds the Gate L2.1 launch/list/detail/
  terminate schema extracts, Lambda billing/termination observations, and the local
  Apple watchdog-source identities. It records no account response or private value.
- `T07_L2_LAUNCH_RECOVERY_DECISION_TEMPLATE.json` is a deliberately invalid,
  fail-closed public record of the decisions the rejected automated design would have
  needed. The user should not materialize it for execution; this repository file is
  not a decision or authorization.
Gate L1A subsequently produced a unique sealed match for `fractal-lambda-codex`.
Gate L2.0 validated and privately sealed the user's type/region/image/key/firewall/
host-key choices. Independent review found that first-party sources cannot guarantee
identification and termination of an accepted launch after an unknown response, and
that the repository lacks one authoritative end-to-end supervisor/evidence path.
That L2.0 historical decision was `blocked-human-or-source-decision`.

Gate L2.1 evaluated that blocked API-launch path with a private random ownership
conjunction, irreversible no-replay state, exact-ID discovery and termination,
fsync-backed transaction/watchdog journals, separate-session cleanup-watchdog
primitives, draft aggregate caps, and complete-evidence checks.
Independent review found
that they are not one authoritative live transaction: effect ordering, shared
cross-process limits/lease, cleanup-on-every-failure, concrete watchdog execution,
terminal polling, exact process arrays, and evidence closure remain incomplete. The
terminal decision is `manual-console-launch-required`. No launch-recovery decision or
executable V2 plan exists, and completing the public decision template would not make
one. Concrete Gate L2.1 HTTPS, subprocess, and watchdog-spawn entrypoints are guarded
to fail before connection, process, pipe, or fork effects; retained tests use fakes.

No `gate-l2-host-qualification-plan.json` is committed. The proposed V1 plan/run
and draft V2 identities are rejected and non-reusable. Gate L2 schemas, renderers,
state helpers, and fake tests are retained only as non-authoritative draft controls.
The terminal disposition is recorded in
`docs/harness/T07_GATE_L2_HOST_QUALIFICATION_AUTHORIZATION_PACKET.md`; it contains no
plan hash or authorization block and permits no current action. A future Gate L2, if
requested, must use a newly reviewed human-operated console topology and fresh
identities.

Gate L2.2 has now evaluated that topology offline. `manual-console/` contains the
sanitized image decision, current first-party source/OCI observations, deliberately
invalid private-decision template, and deterministic Jupyter upload bundle. That
historical gate created no plan.
The existing `img-0111` GPU Base decision lacks a documented JupyterLab guarantee;
`img-0032` / Lambda Stack 22.04 / `22.4.5-2141` is recommended but unselected.
Accordingly Gate L2.2 ended at `blocked-human-image-selection`. Its observer module
is inert on import and exposes only an explicitly constructed, in-process GET
transport plus a status/content/pagination-checking checkpoint engine; it has no
mutation, shell HTTP, SSH, Jupyter, or browser boundary. Request authority and
terminal-ledger capacity are reserved before send; preflight requires five exact
ordered observations; post-send failures burn the run; evidence capabilities are
engine scoped; and sealed output is copied through held local/UTDM descriptors after
source-hash verification. Raw provider bytes are hashed and schema-validated only in
memory; durable private observations are exact allowlisted projections that exclude
Jupyter credentials/URLs and unknown additive scalar fields. The aggregate is 44
read-only GETs, with ten list-only observations each for instance binding and terminal
verification. The bundle also reserves ten calls and 1 MiB of its fixed
Docker-output budget for emergency cleanup. An outcome-unknown create occurs early
enough that unused aggregate headroom additionally covers five identity polls, one
recovered-ID inspect, kill/remove, three stable-absence polls, and final residue proof
without weakening the 32-call aggregate. Its manifest now binds the exact public
BusyBox observation; the driver validates that record and a maximum 86,400-second age
before any Docker call, while separately recording that it makes no live metadata
request. An expired record requires a newly hashed and reviewed bundle. The bundle has
not been uploaded or run.

Gate L2.3 subsequently validated the user's replacement private decision, selected
`img-0032` / Lambda Stack 22.04 / `22.4.5-2141`, resolved raw image/key/firewall/IP
bindings only into ignored sealed evidence, and verified a one-way external copy. The
public decision and marker aliases are `l2m-decision-6b7af4f2c567` and
`l2m-marker-dfc9017f4bc5`; no private scalar or path is public.

`manual-console/gate-l2m-host-qualification-plan-v1.json` remains preserved as
historical provenance. The active executable-but-unauthorized replacement is
`manual-console/gate-l2m-host-qualification-plan-v3.json`: 21,641 bytes, SHA-256
`1931fcacda4194063c0116ff9630d82f3b8f4ec07ff9b0310342335db629f654`, plan
`PLAN-T07-GATE-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-V3`, run
`RUN-T07-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-0003`. It binds the same 23 ordered
actor steps, 13 user checkpoint templates, GET-only observer, exact caps and incident
cleanup while refreshing the reviewed implementation, journal/evidence schemas and
private-seal schema hashes.
User actions remain console-only and automated cloud mutation remains zero. The plan
must start by `2026-08-12T05:15:19.646016Z` after the current-turn authorization
binding; expiry requires a newly reviewed immutable plan. Nothing has been launched,
uploaded, pulled or run; Gate L3 and Gate L4 remain blocked.

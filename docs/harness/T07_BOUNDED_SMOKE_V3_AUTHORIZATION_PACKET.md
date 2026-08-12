# T07 bounded-smoke V3 authorization packet

Status: **ready for a fresh user decision; unauthorized; do not execute from this
packet alone**

## Exact immutable binding

| Field | Exact value |
|---|---|
| Branch | `phase-1/sira-smoke-bounded` |
| Fork / frozen parent | `397a391b736528dd1049023d629100193e823c49` / `t07-high-assurance-infrastructure-v1` |
| Reviewed implementation ancestor | `a7ca7475177aee60126e39c631d61e3d9453ca85` |
| Required execution commit | `<EXACT_FINAL_CLEAN_BOUNDED_SMOKE_V3_PACKET_COMMIT>`; supplied by the final handoff |
| Plan ID | `PLAN-T07-BOUNDED-SIRA-SMOKE-V3` |
| Host run | `RUN-T07-BOUNDED-HOST-0003` |
| Reactive / simulative runs | `RUN-T07-BOUNDED-SIRA-REACTIVE-0003` / `RUN-T07-BOUNDED-SIRA-SIMULATIVE-0003` |
| Future authorization placeholder | `AUTH-T07-BOUNDED-SIRA-SMOKE-V3-PENDING` |
| Plan | `containers/sira-smoke/bounded/bounded-smoke-plan-v3.json` |
| Plan bytes / SHA-256 | 51,401 / `30e83897c476dbd403a55d9d128636443f9df8a787ef903665ece083e3e41a53` |
| Private binding alias / bytes / SHA-256 | `t07-bounded-binding-67eceae4caa9` / 2,660 / `5b06ca70d7821e40574e711b3a68aac6f823b1806d2257395133ced7fc49e96b` |
| Private-binding schema version / bytes / SHA-256 | `0.3.0` / 5,425 / `ee09d8413b44dc66d1cefaad92b81f418e9e0ae0df98413a354a97ea32da350b` |
| OpenAI secret-source schema bytes / SHA-256 | 4,411 / `38cf99ee79532dbc91c85aa8b97868c26351d12c9acc606f315f77257e8d66d4` |
| Plan schema bytes / SHA-256 | 12,768 / `782aad70602e6e9ccb9eef1ffeb7cb5a8a7ce3fd7bef0698acd19a49981128c3` |
| Authorization schema bytes / SHA-256 | 3,293 / `a11268f5abefd590223c370df9467bf3d8d6d641cfa1667c344f569666e464f0` |
| Observer-ledger schema bytes / SHA-256 | 3,315 / `dc62fc35bc730920bf3548cf4cdb5efb5832c1aa3b7fffc7c44d1336e5efd687` |
| Evidence schema bytes / SHA-256 | 1,426 / `05fb95e411eb7fba24fe96ab66323943622d4e10c8c2fcc1a5f2e599283f3e41` |
| Contract module bytes / SHA-256 | 79,119 / `2ef4af297f7d1b8a577d9d6a970d5e678f4e852cd10c4dfa55fd836640f18e43` |
| Local supervisor bytes / SHA-256 | 372,442 / `ae04aa08503366ac63fdd8a05553d63aa1ff5d6566d1cce3aafe69aa7410cc04` |
| Local hash-first bootstrap bytes / SHA-256 | 7,696 / `caa99fe938a3cb0ce67d6dae1e36866abf26f6cf72c109d1ae3ca2f2ea8e7c4d` |
| Remote bootstrap bytes / SHA-256 | 146,919 / `95b83f3ad23498f18cdb8efa90b0661713bf036f06a532ee5edb22f3fe065c4c` |

The V3 plan binds 34 tracked implementation artifacts by exact bytes/SHA-256 and
separately binds the local-only secret-source schema. A tracked document cannot
contain the SHA of the commit that contains itself, so the copy-ready block has one
explicit final-commit placeholder; the final handoff supplies that value. Execution
must verify the clean commit, reviewed ancestry, plan, all 34 artifacts, secret
schema, private binding and its two exact protected upstream seals, science hashes,
and fresh roots before secret or account access.

V1/`0001` and V2/`0002` remain blocked/nonreusable. V2 produced zero run roots,
requests, mutations, checkpoints, billable resources, and secret accesses. V3 is
`authorized: false`; repository permissions and `CMP-0001` actual usage remain zero.

## Secret source and delivery

The exact approved `.env` is classified as repository-external, user-owned,
regular/no-follow, single-link, mode 0644, not group/world writable, ignored in its
source checkout, and private. Its path is represented only by private
`${OPENAI_DOTENV_FILE}` plus plan-bound domain-separated path binding
`77e6457a1a47ee8a62240ffa96dc64c5dc7b7352333c5e67318519c3784ff347`.
It contains one reviewed plain `OPENAI_API_KEY` assignment and one separate
`LAMBDA_API_KEY` assignment. This repair accessed neither value.

- The local Lambda observer may read only `LAMBDA_API_KEY`, once and only after its
  repository/authority/ledger preflight. It rejects ambient OpenAI/SiRA names.
- The OpenAI loader may read only `OPENAI_API_KEY` through
  `giclab-strict-non-shell-dotenv-v1`; no shell, interpolation, fallback, unrelated
  entry, or complete `.env` can cross the channel.
- After post-launch binding and Cloud IDE/Jupyter opening, the user first qualifies
  the exact remote parent: current-user owned, mode 0700, canonical path equal to
  `/home/ubuntu/.config/giclab`, no redirected ancestor, and fresh absent/non-symlink
  final target.
- The supervisor then creates one fresh mode-0600 local filtered file. The user
  uploads only it plus non-release runtime inputs and qualifies the remote file as
  regular, non-symlink, current-user owned, and exact mode 0600.
- The local upload outcome is durably recorded and the exact local device/inode is
  destroyed before the single-use bootstrap release may be issued. Definite or
  ambiguous upload failures use typed abort cleanup and prohibit release; ambiguity
  requires credential rotation.
- The metadata child receives only native `OPENAI_API_KEY`. Each SiRA condition child
  receives the same bytes only as an ephemeral `SIRA_API_KEY` alias. No user-created
  `SIRA_API_KEY` file is required and no process receives both names. Both the remote
  held-descriptor reader and the container entrypoint independently reject a complete,
  multi-line, or otherwise non-token secret file before any provider child.
- Remote cleanup is attempted on every terminal path and must be proven. Before
  provider termination, identity replacement or an unavailable/malformed receipt is
  an incident requiring exact instance termination and conservative manual cleanup.
  Exact terminal/absent proof for the bound instance may prove remote destruction and
  clear rotation that arose only from a missing remote receipt. Detected exposure,
  local cleanup failure, or destruction still unproven after termination requires
  manual cleanup and credential rotation. Missing workload/accounting evidence stays
  unresolved even when termination proves destruction.
- Actual-secret representations are scanned before any untrusted output is hashed or
  retained. No credential value, hash, or derivative may enter argv, labels, paths,
  images, container configuration/evidence, logs, screenshots, ledgers, archives,
  Git, notebooks, chat, or public output.

The V2 private security binding is reusable because it contains no secret source,
path, filename, assignment, value, or derivative. Its ruleset, baseline, restoration,
resource, external seal, alias, bytes, and SHA remain unchanged.

## Fixed scientific/runtime scope

The only prospective scope is one manually supervised `gpu_1x_a10` / `us-east-1` /
`img-0032` Lambda/Jupyter host with zero persistent filesystems; one pinned source and
image build; one no-network Chromium preflight; one exact model metadata GET; then
`SIRA-REACTIVE` once followed by `SIRA-SIMULATIVE` once. Every SiRA role uses
`gpt-4o-2024-11-20`, every Chat Completions request and reconciled response uses
service tier `default`, and interpretation/pilot/training remain false.

The local observer may issue only the 13 plan-listed Lambda GETs, once each in five
ordered phases, without redirect, pagination request, retry, or mutation. Only the
user may change/restore the privately bound firewall, create/delete the owned
regional ruleset, click launch once, open Jupyter, perform exact path-only remote
qualification, upload/download exact files, and terminate the exact instance. SSH is
forbidden.

SiRA remains pinned at commit `93fb8d72de71f9a4a13419670adeb34d93cf7acd`, tree
`6a6d9068b94d7632d3533a3d6f013d4de6ff76e8`, lock SHA-256
`138585129c7f369887591d30d9727f8dd466639fa78fb00adc5a04f1e9b2d76e`,
and routing patch SHA-256
`4d7e2a25f4313fc754db0fa17aeda51cc5cd75a5653adaf13b01ce87a71cb8ed`.
The future install uses pinned uv 0.11.7, `uv sync --frozen --extra eval --python
3.10`, and the digest-pinned Playwright 1.39.0 Jammy image for `linux/amd64`.

## Exact unchanged caps

- OpenAI: USD 4.00 cost and 400,000 tokens aggregate; USD 2.00/200,000 tokens per
  condition; 77 model-call attempts total (16 reactive, 61 simulative); one metadata
  GET; zero retries.
- Conditions: 240 seconds, two browser actions, two attempts, and 209,715,200 retained
  bytes aggregate; 120 seconds, one action/attempt, and 104,857,600 bytes each.
- Containers: four; 128 aggregate lifecycle calls including 48 cleanup-reserved;
  33,554,432 control-output bytes including 8,388,608 cleanup-reserved. Condition
  limits are 2 CPUs, 4,294,967,296 memory bytes with equal memory+swap, 512 PIDs,
  1,073,741,824 shm bytes, 134,217,728 tmpfs bytes, one 8,388,608-byte log file,
  five-second TERM, restart `no`, and 120 seconds cleanup reserve.
- Lambda: one instance, one launch click, zero persistent filesystem, USD 2.00 normal
  cost, projected USD 1.29, 3,600-second provider/authorization wall, termination
  click by 3,300 seconds.
- Lambda observer: 13 GETs; 1,048,576 bytes each/13,631,488 aggregate; 262,144-byte
  ledger, 96 events, 4,096 bytes/event, 3,600 seconds.
- Setup/storage/evidence: 2,147,483,648 setup-transfer admission bytes;
  17,179,869,184 runtime-disk bytes; 34,359,738,368 remote-free floor;
  268,435,456 remote evidence bytes; 301,989,888 local/external archive bytes;
  1,048,576 early-failure bytes; 128 total archive files; 600 archive seconds;
  8,388,608 upload bytes and 36 upload members. A complete archive has exactly 39
  payload plus three seal files; the hard cap remains 125 plus three.
- Storage floors: Mac prewrite/retained 8,891,924,480 / 8,589,934,592 bytes;
  external prewrite/retained 200,350,182,605 / 200,048,192,717 bytes.
- Automatic/implicit retries and supervisor cloud mutations: zero.

## Cleanup and archive contract

Success or failure preserves only safe bounded evidence; captures process/payload
evidence before immutable-ID removal; stop/kill escalates as needed; and proves zero
owned container/network/volume/browser residue. The user terminates the exact bound
instance and the observer proves terminal/nonbillable state before the user deletes
only the owned ruleset and restores the exact sealed global baseline. Unknown release
upload/bootstrap outcomes keep OpenAI usage/cost unreconciled even after exact
instance termination; missing evidence is never rewritten as zero usage.

The final archive admits only its exact typed source set. It verifies the local
secret lifecycle, inbound evidence or conservative no-inbound incident state,
observer ledger, termination, firewall restoration, and billing/security closeout,
then copies one way through held APFS/UTDM descriptors, rereads/hashes every
destination, fsyncs, atomically finalizes, retains source, and forbids internal
fallback. No failure or ambiguous send authorizes replay.

## Ready-to-copy V3 authorization block

Replace only the final clean commit placeholder and, if used later, the date suffix.
Any code, plan, schema, binding, source syntax, resource, price, storage, or science
drift requires another reviewed packet.

```text
I authorize T07 bounded SiRA smoke V3 only on exact clean commit
<EXACT_FINAL_CLEAN_BOUNDED_SMOKE_V3_PACKET_COMMIT> of branch
phase-1/sira-smoke-bounded, descended from reviewed implementation commit
a7ca7475177aee60126e39c631d61e3d9453ca85 with all 34 tracked plan-bound
implementation artifact hashes and separately bound OpenAI secret-source schema
SHA-256 38cf99ee79532dbc91c85aa8b97868c26351d12c9acc606f315f77257e8d66d4
unchanged, using plan PLAN-T07-BOUNDED-SIRA-SMOKE-V3 at
containers/sira-smoke/bounded/bounded-smoke-plan-v3.json, 51,401 bytes, SHA-256
30e83897c476dbd403a55d9d128636443f9df8a787ef903665ece083e3e41a53,
host run RUN-T07-BOUNDED-HOST-0003, reactive run
RUN-T07-BOUNDED-SIRA-REACTIVE-0003, simulative run
RUN-T07-BOUNDED-SIRA-SIMULATIVE-0003, fresh authorization reference
AUTH-T07-BOUNDED-SIRA-SMOKE-V3-2026-08-12, and protected private security binding
alias t07-bounded-binding-67eceae4caa9, 2,660 bytes, SHA-256
5b06ca70d7821e40574e711b3a68aac6f823b1806d2257395133ced7fc49e96b.

I authorize materialization of the exact pre-sealed private binding only after its
protected path/local-seal SHA and external bundle pass the plan's held-descriptor
checks; one fresh 3,600-second single-run overlay; the exact tracked-only
36-member/8,388,608-byte repository upload archive and reviewed bootstrap; exactly
the 13 GET-only Lambda observations; and only the plan-listed user console actions:
temporary private global-firewall restriction, one owned regional ruleset, one manual
launch click for gpu_1x_a10/us-east-1/img-0032 with no persistent filesystem, Cloud
IDE/Jupyter, exact path-only remote qualification, exact upload/download, termination
of the bound instance, deletion of only the owned ruleset, and exact firewall
restoration.

The operator may access LAMBDA_API_KEY only through the approved nonlogging local
Lambda channel after its preflight. After post-launch binding and opening Jupyter,
the operator must first prove the exact remote parent is current-user-owned mode 0700,
canonical with no redirected hierarchy, and the secret target is fresh and absent.
The operator may then access only the OPENAI_API_KEY assignment from the exact
previously qualified repository-external private .env supplied as
${OPENAI_DOTENV_FILE}, using the strict non-shell no-follow parser. I authorize the
supervisor to create one single-run mode-0600 filtered local file; the user to upload
only that file plus the non-release runtime inputs; the user to prove the remote file
is regular, non-symlink, current-user-owned and exact mode 0600; and the supervisor to
commit the upload outcome and destroy the exact local device/inode. Only after
positive cleanup may the supervisor issue and the user upload the bootstrap release.
Definite or ambiguous upload failure authorizes only typed local abort cleanup,
instance/security cleanup, evidence sealing, and rotation when required—not release
or execution.

The complete .env and LAMBDA_API_KEY must not be uploaded. No user-created
SIRA_API_KEY file is required. The metadata child may receive the selected bytes only
as OPENAI_API_KEY; each SiRA condition child may receive them only as an ephemeral
SIRA_API_KEY alias. There is no provider-credential fallback. No credential value,
hash, or derivative may enter argv, labels, paths, images, environment/configuration
evidence, logs, screenshots, ledgers, archives, Git, notebooks, chat, or public
output.

I authorize one pinned source/image/dependency build, one no-network local-static-page
Chromium preflight, one GET of
https://api.openai.com/v1/models/gpt-4o-2024-11-20, then SIRA-REACTIVE once followed
by SIRA-SIMULATIVE once, using gpt-4o-2024-11-20 for every role and
service_tier="default" on every request and reconciled response.

Caps are USD 4.00 OpenAI aggregate/USD 2.00 per condition; 400,000/200,000 model
tokens; 77 model-call attempts total (16/61); one browser action, 120 seconds,
104,857,600 retained-output bytes, and one attempt per condition; zero retry; one
Lambda instance, one launch click, zero persistent filesystem, USD 2.00 normal cost,
3,600 seconds with termination click by 3,300 seconds; 13 Lambda GETs;
2,147,483,648 setup-transfer admission bytes; 17,179,869,184 runtime-disk bytes;
268,435,456 remote evidence bytes; 301,989,888 local/external archive bytes; 128
aggregate Docker lifecycle calls; and every exact CPU, memory, PID, tmpfs, log,
output, observer, wall, and storage cap in the plan.

I authorize the exact success-or-failure evidence capture and one-way hash-verified
archive copy to the approved APFS/UTDM root with source retention, held no-follow
identity checks, exact floors, fsync, atomic finalization, and no internal fallback.
On any stop condition, do not retry: preserve safe evidence, attempt and verify secret
and owned-container cleanup, terminate the exact bound instance, verify
terminal/nonbillable state, remove only the owned ruleset, and restore the exact
firewall baseline. When the remote cleanup receipt is absent or invalid, exact
terminal/absent proof for the bound instance may prove remote credential destruction;
require credential rotation for detected exposure, local cleanup failure, or
destruction still unproven after termination. Unknown OpenAI execution remains
unreconciled rather than being recorded as zero. Stop after the pair or first terminal
failure. This grants no pilot, training, interpretation, T08, unrelated mutation,
SSH, second launch, second condition attempt, or production claim.
```

## Remaining blockers

The authorization blocker is a fresh user message containing the exact final clean
packet commit and completed block. Dynamic resource/model/price/secret-source/
storage/freshness/user-presence/termination checks remain execution-time hard
blockers. No other code or configuration repair is presently known.

No Lambda/OpenAI/public-IP request, real-secret access, cloud mutation, paid compute,
SSH, Jupyter, container, browser, SiRA condition, or scientific execution occurred
while preparing this packet.

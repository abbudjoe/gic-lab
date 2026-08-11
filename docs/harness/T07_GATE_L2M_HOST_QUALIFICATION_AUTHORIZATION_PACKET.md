# T07 Gate L2M host-qualification authorization packet

Status: **ready-for-manual-console-qualification-authorization; unauthorized**

Date: 2026-08-11

## Exact immutable identities

| Item | Identity |
|---|---|
| Branch | `phase-1/sira-smoke-lambda` |
| Required final clean execution commit | `<EXACT-FINAL-CLEAN-GATE-L2-3-HANDOFF-COMMIT>`; supplied in the final handoff and fresh user authorization |
| Reviewed implementation commit | `9ccc46b49f18558af5645cdb390ae669c484373e` |
| Plan ID | `PLAN-T07-GATE-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-V1` |
| Run ID | `RUN-T07-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-0001` |
| Plan path | `containers/sira-smoke/lambda/manual-console/gate-l2m-host-qualification-plan-v1.json` |
| Plan bytes | 21,638 |
| Plan SHA-256 | `fce83fae57cea8b8d1010673b93bf496be2990771faa0dc4986c18c8b0bd1648` |
| Pending reference | `AUTH-T07-GATE-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-V1-PENDING` (not executable authority) |
| Decision alias | `l2m-decision-6b7af4f2c567` |
| Decision source SHA-256 | `1b603e4bfb1e63b9046bb5b3d404a083666e7a28437e63a20613d7321063bad4` |
| Decision canonical SHA-256 | `6b7af4f2c567f8c8e66f3d165e8ffbc144028cf3edf45727bb569e254c7bb75f` |
| Private decision seal SHA-256 | `2516d9d902c225f3576e7be193a772b27eb208a85fd4ac63b7d9faa3a101eff6` |
| Private parameters SHA-256 | `cfd40a341759d3a52f7c3161d1f28002d8f4945fbdf1cf62e69e2fccfb76f6b6` |
| Private bundle seal SHA-256 | `10f4f1798b11593528088c6ceff47418b6d6c3baa7b9caa3d74c1de1dd314c48` |
| Marker alias | `l2m-marker-dfc9017f4bc5` |
| External archive alias | `l2m-archive-abdfb6a398ac` |
| External copy/seal SHA-256 | `3436784c72bb01bce0e0e6fc0b1c42e08e26cb106d5306a9b50f8c8b8f7b1c2d` / `5b1fea4933b1d42db51925af7ab6112826de26912a707bf36a29962b6fe79f95` |

The plan itself remains `authorized: false`, `cloud_mutation_allowed: false`,
`paid_compute_allowed: false`, `prototype_execution_allowed: false` and
`scientific_interpretation_allowed: false`. A future user authorization is an
external, one-run authority binding; the plan is never edited in place.

## Selected public resources

- Provider/API: Lambda On-Demand Cloud at `https://cloud.lambda.ai`.
- Architecture/type/region: `x86_64`, `gpu_1x_a10`, `us-east-1`.
- Image: `img-0032`, `lambda-stack-22-04`, `22.4.5-2141`.
- SSH-key name: `fractal-lambda-codex`, launch-wizard input only; SSH use is zero.
- Persistent filesystem: none.
- Access: user-operated Lambda Cloud IDE/Jupyter only.
- Qualification image:
  `busybox@sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0`,
  `linux/amd64`, config
  `sha256:db287cb6be81219cd18c1d82b70908f5d33eb028568b456f78eedff2ff2930e4`,
  one 2,211,507-byte compressed layer
  `sha256:436a1b1fd078ee8e117111472724c2827077657189af7a781829d0825d48d2ab`.

Static sources do not prove that the selected image is offered for the exact
type/region or that Cloud IDE works under the strict firewall. Offeredness is the
first user checkpoint before mutation. Either empirical mismatch stops without
substitution, extra ports or SSH.

## Bound schemas and bundle

| Artifact | SHA-256 |
|---|---|
| Private decision seal schema | `e4bc66c5759fe700e62ba2bb54dec1c509c68f7f63308170195c6454c607ca3f` |
| User checkpoint schema | `a55f9023f8cc8f530acebe31bbe7b50c57d1e1a01b959ced38876e43e0f108ff` |
| Observer journal schema | `c9d5fef455c35ce0e8f957fe54040464a641ce10a57a95feadb09f24d3c1bf9f` |
| Host-evidence schema | `8311ff4dcc82df5bf8272f549119c13fa37baf9ef46e41cea5c3629b11253ef3` |
| Qualification manifest | `dc9824649f97fab6cfd105b5fc0d0c6c1c5ff513fa25f70e0d517afa623cc261` |
| Qualification driver | `ab9a3f8981d2e60ea5b57bb7cf63512f64cdb89f26d8183788aedc2dbe4b5050` |

The manifest is
`containers/sira-smoke/lambda/manual-console/manifest.json`, 1,510 bytes. It binds
all six bundle members. The plan separately binds the exact implementation, bootstrap,
all 13 checkpoint templates and schema hashes.

## Exact observer and request contract

The observer invocation is a shell-free array from the clean repository root:

```json
[
  ".venv/bin/python",
  "-I",
  "containers/sira-smoke/lambda/manual-console/l23_supervisor_bootstrap.py",
  "--repository-root", ".",
  "--plan", "containers/sira-smoke/lambda/manual-console/gate-l2m-host-qualification-plan-v1.json",
  "--plan-sha256", "fce83fae57cea8b8d1010673b93bf496be2990771faa0dc4986c18c8b0bd1648",
  "--expected-commit", "<EXACT-FINAL-CLEAN-GATE-L2-3-HANDOFF-COMMIT>",
  "--authorization-reference", "<FRESH-AUTHORIZATION-REFERENCE>",
  "--authorization-sha256", "<SHA256-OF-THE-FRESH-USER-AUTHORIZATION-TEXT>"
]
```

The exact transport is the in-process
`giclab.harness.lambda_l2m_observer.LambdaHttpsL2MObserverTransport`. It permits GET
only to host `cloud.lambda.ai`, no query, across these exact path forms:

```text
/api/v1/images
/api/v1/instance-types
/api/v1/ssh-keys
/api/v1/instances
/api/v1/instances/{private-bound-instance-id}
/api/v1/firewall-rulesets
/api/v1/firewall-rulesets/{private-bound-ruleset-id}
/api/v1/firewall-rulesets/global
```

It has no POST/PATCH/DELETE path. Curl, wget, shell HTTP, redirect follow,
pagination and retry are prohibited. Every request is durably reserved and journaled
before send. The sole secret variable is `LAMBDA_API_KEY`, read in process only after
all nonsecret preflight passes and never printed, hashed, persisted, returned or
inherited by a child. `SIRA_API_KEY` and `OPENAI_API_KEY` are forbidden.

## Exact numeric caps

| Category | Exact cap |
|---|---:|
| Read-only Lambda GETs | 44 |
| Per-GET response bytes | 1,048,576 |
| Aggregate response bytes | 16,777,216 |
| Private observation files / bytes each / aggregate | 44 / 1,048,576 / 16,777,216 bytes |
| Minimum request-start spacing | 1 second |
| Preflight GETs | 6 |
| Original-global-seal GETs | 1 |
| Restricted-global verification GETs | 1 |
| Regional-ruleset bind GETs | 1 |
| Instance-bind GETs | 9 |
| Cloud IDE / qualification GETs | 0 / 0 |
| Terminal verification GETs | 10 |
| Regional-ruleset absence GETs | 2 |
| Global-restoration GETs | 1 |
| Incident GETs | 13 |
| Observer events / bytes each / journal | 512 / 4,096 / 2,097,152 bytes |
| Observer active / prelaunch / post-provider cleanup / archive / total wall | 6,000 / 1,200 / 1,200 / 300 / 6,300 seconds |
| Per-request observer wall | 60 seconds |
| Launch-to-active / Cloud IDE | 600 / 600 seconds |
| Qualification / download-validation | 300 / 300 seconds |
| Normal termination click / terminal verification / firewall cleanup | 1,800 / 600 / 300 seconds |
| Incident headroom | 900 seconds |
| Local process calls / output | 16 / 4,194,304 bytes |
| Provider hard wall / cost | 3,600 seconds / USD 2.00 |
| Modeled normal/hard-wall list cost | 86 / 129 cents |
| User checkpoint window | 300 seconds each |
| Launch clicks / normal instances / filesystems | 1 / 1 / 0 |
| Qualification files / ZIP / unpacked | 16 / 16,777,216 / 33,554,432 bytes |
| Remote retained source / archive / aggregate | 34,603,008 / 33,554,432 / 68,157,440 bytes |
| Mac active evidence | 83,886,080 bytes |
| External sealed archive | 41,943,040 bytes |
| Docker total / ordinary / cleanup-reserved calls | 32 / 22 / 10 |
| Docker per-call / aggregate / ordinary / cleanup-reserved output | 1,048,576 / 8,388,608 / 7,340,032 / 1,048,576 bytes |
| Qualification containers | 1 |
| Fixture / ordinary Docker / cleanup-inclusive wall | 30 / 270 / 300 seconds |
| Create-outcome poll / stable-absence observations / spacing | 5 / 3 / 1 second |
| Container CPU / memory / swap / PIDs | 1.000 / 536,870,912 / 536,870,912 bytes / 64 |
| Container `/tmp` / `/run` / shm | 16,777,216 / 16,777,216 / 16,777,216 bytes |
| Container local log | 1,048,576 bytes × 1 file |
| BusyBox compressed layer | 2,211,507 bytes |
| Automatic retries / pagination / redirect follows | 0 / 0 / 0 |
| Automated cloud mutations | 0 |
| SSH operations | 0 |
| Browser automation actions | 0 |
| Model calls / tokens | 0 / 0 |
| SiRA executions | 0 |

The normal user termination click is due by 1,800 seconds after Launch. Terminal
proof has at most 600 seconds and firewall cleanup 300 seconds within the hard
provider wall. A provider/control-plane outage can defeat local wall/cost ceilings;
the private user decision explicitly acknowledges that residual billing exposure.

## Storage and evidence contract

The active Mac mini evidence cap is 83,886,080 bytes. Prewrite free space must be at
least 8,725,200,896 bytes and retained free space at least 8,589,934,592 bytes. The
one-way archive target is `/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts`,
bound through held no-follow descriptors to APFS Data UUID
`8478609D-FA37-4ED5-875D-47AE912B9151` and physical-store UUID
`7904A6F1-F483-4ED7-9E34-BFECAB31C63E`. The dynamic external floor must include the
41,943,040-byte archive cap. No symlink traversal or internal fallback is allowed.

The observer holds the checkpoint, challenge, inbound and evidence roots throughout
sensitive operations; validates regular files, link counts, ownership, mode, exact
bytes and hashes; fsyncs files and directories; atomically finalizes the destination;
reopens through held descriptors; verifies every destination hash; and retains the
local source. Partial evidence is preserved and cannot become an eligible Gate L3
receipt.

## Exact user-only mutation sequence

Under a future authorization, the user—and never the observer—may perform only:

1. offeredness check with no launch;
2. exact global replacement with TCP/22 from the private `/32`;
3. creation of one fresh `us-east-1` ruleset with that same sole rule;
4. exact launch-configuration selection with no filesystem;
5. exactly one Launch click;
6. Cloud IDE/Jupyter open for the uniquely bound instance;
7. exact bundle upload;
8. one hash-first qualification command and no rerun;
9. one evidence archive download;
10. termination of the exact bound or ruleset-attached incident scope;
11. deletion of the exact owned regional ruleset after terminal proof; and
12. exact restoration of the sealed original globals after ruleset absence.

The 13 single-use checkpoint templates separately attest offeredness, global
restriction, ruleset creation, launch selection, launch click, Cloud IDE, upload,
command start, command completion, archive download, termination when applicable,
ruleset deletion and global restoration. Exact instance binding and terminal proof are
observer-only durable receipts.

## Incident/stop rules

1. No workload on zero, multiple or drift; never make a second launch click.
2. Termination authority includes only the exact bound instance or private IDs proven
   attached to the unique owned ruleset. An unattached account row is not inferred to
   be T07; preserve the strict firewall and require a new human decision.
3. Do not restore permissive global rules until the authorized instance scope is
   terminal/absent and the owned ruleset is absent.
4. Cloud IDE failure opens no port and permits no SSH.
5. Qualification or evidence failure permits cleanup only and never a rerun.
6. A control-plane outage preserves the strict firewall, permits no replacement
   launch and records residual billing exposure.
7. Observer exit/restart after live work burns the run identity; preserve its exact
   ledger prefix and require separately authorized recovery.
8. Archive unavailability preserves the local source and never uses internal fallback.
9. Cleanup targets no unrelated instance, rule, key, filesystem, image or evidence;
   no broad prune or delete is permitted.
10. Any branch/commit/hash/seal/storage/floor/credential/metadata-age/cap/checkpoint/
    response/evidence mismatch stops at the earliest safe boundary.

## Remaining blockers

1. A fresh user turn must authorize the exact final clean handoff commit, plan/hash,
   reviewed implementation, run, decision aliases/hashes, observer GETs, manual
   console mutations, credential channel, one digest-pinned BusyBox pull/container,
   provider cost/wall, evidence copy and cleanup.
2. The supervisor must start no later than `2026-08-12T05:15:19.646016Z`. Expiry
   requires a new public metadata record, bundle, plan, review and authorization.
3. The run/checkpoint/inbound/external final identities must still be fresh; repository,
   private seals, credential presence, mount identities and floors must pass again.
4. The user must remain present for the full billable/cleanup window, and the
   launch-wizard image offeredness and strict-firewall Cloud IDE checks remain
   empirical stop conditions.
5. Gate L3 and Gate L4 remain separately blocked and unauthorized even after a
   successful Gate L2M.

## Ready-to-copy authorization block

The final handoff must replace the marked clean commit before the user sends this in a
fresh turn. The operator computes and binds the SHA-256 of the exact received
authorization text; that digest is evidence, not text to be guessed here.

```text
Continue T07 with Gate L2M manual-console host qualification only.

I authorize exact plan PLAN-T07-GATE-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-V1,
run RUN-T07-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-0001, at
containers/sira-smoke/lambda/manual-console/gate-l2m-host-qualification-plan-v1.json,
21,638 bytes, SHA-256
fce83fae57cea8b8d1010673b93bf496be2990771faa0dc4986c18c8b0bd1648, on branch
phase-1/sira-smoke-lambda at exact clean commit
<EXACT-FINAL-CLEAN-GATE-L2-3-HANDOFF-COMMIT>. Reviewed implementation commit
9ccc46b49f18558af5645cdb390ae669c484373e must be an ancestor and every plan-bound
artifact hash must remain exact. Use authorization reference
AUTH-T07-GATE-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-V1-2026-08-11 and start the
supervisor no later than 2026-08-12T05:15:19.646016Z.

The sealed decision is l2m-decision-6b7af4f2c567, source SHA-256
1b603e4bfb1e63b9046bb5b3d404a083666e7a28437e63a20613d7321063bad4, canonical
SHA-256 6b7af4f2c567f8c8e66f3d165e8ffbc144028cf3edf45727bb569e254c7bb75f,
with private-parameter SHA-256
cfd40a341759d3a52f7c3161d1f28002d8f4945fbdf1cf62e69e2fccfb76f6b6 and marker
alias l2m-marker-dfc9017f4bc5. No private scalar may be printed or copied into Git.

I authorize the exact in-process GET-only observer to access only LAMBDA_API_KEY
through the documented nonlogging secret channel and make at most 44 GETs to
https://cloud.lambda.ai using only the plan's exact eight path forms, one-second
minimum starts, no query, retry, pagination, redirect follow or HTTP subprocess. I
authorize no automated cloud mutation. SIRA_API_KEY and OPENAI_API_KEY remain
forbidden.

I authorize the user, through the Lambda console only, to confirm offeredness without
launch; replace the global firewall with exactly TCP/22 from the private /32; create
one exact fresh us-east-1 regional ruleset; select gpu_1x_a10, us-east-1, img-0032 /
22.4.5-2141, no filesystem, fractal-lambda-codex and that ruleset; click Launch
exactly once; use Cloud IDE/Jupyter only; upload the exact manifest-bound bundle; run
the hash-first qualification command exactly once; download one evidence archive;
terminate only the exact bound or ruleset-attached incident-scope instances; delete
only the owned ruleset after terminal proof; and restore the exact sealed original
global firewall after ruleset absence. SSH and extra firewall ports are prohibited.

I authorize one pull, capped at the bound 2,211,507-byte compressed layer, of
busybox@sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0
for linux/amd64 and one no-network qualification container through the exact bundle.
Docker is limited to 32 calls total, 22 ordinary and ten cleanup-reserved; one
container; 1,048,576 bytes per call; 8,388,608 bytes aggregate, with 7,340,032
ordinary and 1,048,576 cleanup-reserved; 30 fixture seconds, 270 ordinary-work seconds
and 300 seconds including cleanup. The container is capped at 1 CPU, 536,870,912
bytes memory/swap, 64 PIDs, two 16,777,216-byte tmpfs mounts, 16,777,216-byte shm and
one 1,048,576-byte local log. No install, runtime update, browser, model or SiRA action
is authorized.

Observer caps are 44 GETs; 1,048,576 bytes per response/private observation;
16,777,216 aggregate response/private-observation bytes; 512 events; 4,096 bytes per
event; 2,097,152 journal bytes; 16 local process calls; 4,194,304 local-process output
bytes; 60 seconds per request; 6,000 active seconds partitioned into 1,200 prelaunch,
3,600 provider and 1,200 post-provider cleanup, plus 300 archive seconds and 6,300
total. Phase deadlines are 600 seconds launch-to-active, 600 Cloud IDE, 300
qualification, 300 download-validation, 1,800 normal termination click, 600 terminal
verification, 300 firewall cleanup and 900 incident headroom.

Evidence caps are 16 files; 16,777,216 bytes per source/archive set; 34,603,008 remote
source bytes; 33,554,432 remote archive bytes; 68,157,440 remote aggregate bytes;
41,943,040 local source and sealed bytes each; 83,886,080 Mac-active bytes; and
41,943,040 external sealed-archive bytes. Provider caps are 3,600 seconds, USD 2.00,
one Launch click, one normal instance and zero persistent filesystems. Automatic
retries, pagination, redirects, automated mutations, SSH operations, browser
automation, model calls, model tokens and SiRA executions are all zero.

Revalidate and hold the approved external mount with APFS UUID
8478609D-FA37-4ED5-875D-47AE912B9151 and physical-store UUID
7904A6F1-F483-4ED7-9E34-BFECAB31C63E, enforce the 8,725,200,896-byte Mac prewrite
floor, 8,589,934,592-byte retained floor and dynamic external floor plus 41,943,040
bytes, prohibit internal fallback, verify every source/destination SHA-256, fsync,
atomically finalize, and retain the local source.

Stop before mutation on any preflight/offeredness drift. After a launch click, run no
workload on zero/multiple/drift, never click Launch again, preserve strict firewall on
outage or ambiguity, never infer authority over an unattached account row, never
rerun qualification, and complete only the exact authorized cleanup. Observer restart
burns the run identity. Stop after Gate L2M evidence sealing.

This authorization permits infrastructure qualification only. It does not authorize
Gate L3, Gate L4, the EXP-0001 pair, any model/provider-model call, browser action,
SiRA execution, scientific interpretation, pilot, training, unrelated cloud mutation
or reuse of this authority.
```

Gate L2M has not been authorized or executed by this packet.

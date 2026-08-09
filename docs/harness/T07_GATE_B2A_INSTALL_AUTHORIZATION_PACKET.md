# T07 Gate B2a install and storage-binding authorization packet

Status: **blocked; this packet and its plan authorize nothing**

Prepared: 2026-08-09

## Exact repository and plan identity

- Branch: `phase-1/sira-smoke`
- Gate B1.6 implementation commit:
  `321136b2a23158a7618e1489a4d2005d7f7ba1cd`
- Gate B1.6 baseline:
  `e224e781e752869041c78a3e93687aaa5d8c6430`
- Plan ID: `PLAN-T07-GATE-B2A-DOCKER-STORAGE-QUALIFICATION-V1`
- Plan path:
  `containers/sira-smoke/gate-b2a-install-storage-binding-plan.json`
- Plan SHA-256:
  `7ccd43e413ec8c4a21a4af043bef2477ede14b5bd40885c979cdeb7e48081eb1`
- Authorization placeholder: `AUTH-T07-GATE-B2A-PENDING`
- Plan status/value: `blocked-design-only`; `authorized=false`

The implementation commit is an ancestor of the packet commit. A Git document cannot
contain its own final commit SHA without changing that SHA; the clean packet commit is
reported at handoff. Any code change after the bound implementation commit requires a
new implementation binding and plan hash.

## Selected product and current verification status

No Docker/OCI runtime is installed or running. The selected candidate remains exactly:

```text
Product: Docker Desktop for Mac, Apple silicon
Version/build: 4.85.0 / 235549
Platform: macos/arm64
URL: https://desktop.docker.com/mac/main/arm64/235549/Docker.dmg
Bytes: 573592444
SHA-256: 84b1224c93456fe261955ebc91f3cd88ce19778ffdb6d0a0d423ce37246f7c2b
Retained ETag: 4f9b2b18fabbf15788279792b6ea69a8
Retained object version: wsuDysIsQ5IOyQOhS5596yFr.2s94QxI
Retained minimum macOS: 14.0.0
```

Official appcast/checksum/object evidence was observed on 2026-08-09, but it was not
freshly reverified in this no-network turn. The future metadata verifier binds the
matching appcast item/enclosure—not the channel link—to build, version, URL, bytes,
minimum macOS, and checksum. Drift stops before the DMG download.

Expected network endpoints in a resolved Gate B2a are only
`https://desktop.docker.com/mac/main/arm64/appcast.xml`,
`https://desktop.docker.com/mac/main/arm64/235549/checksums.txt`, and the exact DMG URL
above. Docker Desktop first-start/terms/update endpoints are not locally established;
that unknown blocks authorization. No registry, source repository, package index,
Playwright/Chromium CDN, provider, or model endpoint is approved in B2a.

## Exact storage roots and floors

| Role | Exact value |
|---|---|
| Docker Linux disk/image/layer/container/build cache | `/Volumes/Macintosh HD - Data/GIC-Lab/t07/docker-desktop/disk-image` |
| Future Docker/build staging | `/Volumes/Macintosh HD - Data/GIC-Lab/t07/docker-build-staging` |
| Sealed artifact archive | `/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts` |
| Mac mini active attempts | `/Users/joseph/.local/share/gic-lab/t07-gate-b2a/attempts` |
| Mac mini B2a work/evidence | `/Users/joseph/.local/share/gic-lab/t07-gate-b2a` |
| External retained-free floor | 200,048,192,717 B |
| External pre-B2a floor | 212,933,094,605 B |
| External incremental cap | 12,884,901,888 B |
| Mac mini numeric floor | **unresolved; no value issued** |
| Mac mini incremental cap | **unresolved; null and authorization-blocking** |

The Mac mini exact floor equation is
`H_os + D_download_peak + A_app + S_support + U_update_rollback + E_active +
F_failure + I_first_start_internal`. Only `D_download_peak=573,592,444` and
`E_active=67,108,864` are exact. The external volume had 854,038,691,840 free bytes
at `2026-08-09T15:59:33Z`. The system volume had 29,444,337,664 free bytes then, but
an observed free value cannot clear an unresolved floor.

The volume guard binds APFS Data UUID
`8478609D-FA37-4ED5-875D-47AE912B9151`, physical-store UUID
`7904A6F1-F483-4ED7-9E34-BFECAB31C63E`, exact mount, writable/unlocked state,
Thunderbolt/UTDM transport, external device role, floor, and no-symlink exact paths.
There is no internal fallback.

## Exact caps and action counts

- Aggregate wall: 7,200 seconds; per-step sum 6,240 seconds.
- Aggregate captured output: 16,777,216 bytes; per-step sum 7,839,744 bytes.
- Aggregate download: 577,786,748 bytes: two 2,097,152-byte metadata caps plus the
  exact 573,592,444-byte DMG.
- External incremental disk: 12,884,901,888 bytes.
- Active attempt evidence: 67,108,864 bytes.
- B2a evidence/sealed copy: 16,777,216 bytes.
- API cost: USD 0 aggregate and per action.
- Model tokens/calls: 0 aggregate and per action.
- Experimental browser: 0 steps/actions and 0 browser screenshots.
- Docker Settings GUI/physical controls: 9 user-only actions total, including one
  cropped settings evidence image; no automated click or terms acceptance.
- Automatable child calls: exactly 66, including 24 adjacent storage guards; total
  plan steps: 75; retries: 0.
- System disk cap: unresolved/null; therefore no action is authorized.

Every per-action wall/output/download/internal/external disk cap and all 66 exact argv
arrays are in the hashed plan. A null value is a stop condition, never permission for
unbounded use.

The implemented `B2AExecutionSupervisor` refuses this `authorized=false` plan and any
plan with unresolved system caps. For a future replacement it enforces exact order,
one execution per action, the exact automatable-call ceiling, monotonic per-action and
aggregate deadlines, expected stdout where declared, output/download/disk-delta caps,
both free-space floors, the active-attempt cap, adjacent single-use guard consumption,
zero retry, and complete action accounting. It can mint one in-memory, single-use
close capability only after an exact writer probe reports zero. The standalone
seal/copy CLI is disabled until an authorized in-process driver binds that capability.

## Exact automatable and user-only actions

The ordered automatable groups are repository/volume preflight; 24 action-adjacent
typed storage guards; fresh-root creation; two official metadata downloads and
verification; exact DMG download/verification; app-absence, attach, `ditto` install,
detach; two exact guarded Docker starts; installed app and minimized engine/context
inspection; pre/post-reconnect volume/engine inspection; and sealed one-way evidence
copy. The machine-readable plan is authoritative for each shell-free array.
Repository status must emit exactly an empty string, branch must emit exactly
`phase-1/sira-smoke`, the implementation commit must be an ancestor, and `git diff
--quiet` must prove the seven bound implementation/schema files and five locked
scientific files equal the bound commit.

The user alone must:

1. Personally review and accept applicable terms.
2. Establish the version-specific supported no-update/no-substitution setting before
   engine start, or stop.
3. Select the exact external directory through Settings -> Resources -> Advanced ->
   Disk image location.
4. Use Apply/Restart once after the guard.
5. Permit one cropped location/version-only settings image.
6. Quit Docker and wait for machine-confirmed stopped/no-open-file state.
7. Eject and disconnect Target Disk Mode.
8. Reconnect, remount, and unlock without starting Docker.
9. Quit finally before evidence sealing.

The plan renders both otherwise-standalone Docker starts as exact automated
`/usr/bin/open -na /Applications/Docker.app` actions directly after typed guards. The
user-only Apply/Restart action remains separate because it is a product GUI control.

User attestations cover actions/timestamps only. Machine evidence must prove placement,
engine identity, same-disk reopen, default-internal inactivity, and cleanup.

## Installation, dependencies, browser, and secret actions

The proposed installation uses a read-only DMG attach, exact
`/Volumes/Docker/Docker.app` to `/Applications/Docker.app` `ditto`, then detach. It is
blocked and did not run. No base image pull, image build, SiRA dependency, Playwright,
Chromium, browser, container, or provider/model action exists in B2a. Their exact
authorized counts are zero.

No secret variable or secret value is required in B2a. `SIRA_API_KEY` and
`OPENAI_API_KEY` remain rejected/out of scope, and neither was read. Any future B2b
dummy-secret design remains undesigned.

## Reconnect and placement evidence

Docker must be fully stopped before eject. After reconnect, both stable UUIDs and the
exact mount/paths are re-resolved; device numbers may change. A new guard must pass
before restart. The version-verified persisted location extract, exact VM file
identity/stat/open-file evidence, minimized Docker version/info/context, default
internal absence/inactivity, and same external disk healthy reopen must all agree.
Docker is stopped again before sealing. Failure blocks B2b.

These are required observations, not current supervisor proofs. The V1 state machine
does not yet bind machine stopped/open-file evidence, version-specific placement
outputs, or a fresh mount-identity observation at restart. Those gaps block a
replacement executable plan.

The `noowners` mount remains a residual risk: it can be qualified for one opaque VM
disk and nonsecret hashed artifacts, but it is not a host confidentiality boundary and
is not approved for live attempt roots or real secret files.

## Cleanup contract

Stop on first failure with zero retry. The declared cleanup requires one clean DMG
detach if mounted and requires the user to Quit Docker if running, followed by
machine-verifiable stopped state. Do not automatically
uninstall Docker, delete or move a default internal VM disk, delete external Docker
state, remove a user file, reuse an identity, or delete local evidence. Preserve failed
staging. Seal/hash/fsync local B2a evidence, qualify fresh typed source and destination
volume/path identities, copy through a fresh external staging identity, verify every
destination hash, make finalized files/directories read-only, atomically finalize,
retain the copy record, and retain the local source. The rollback array is hash-bound
but is not yet a typed fail-state executor, so none of those cleanup actions is
presently authorized or claimed mechanically enforced.

## Unresolved authorization blockers

1. Current official metadata has not been freshly reverified.
2. Six Mac mini floor terms and the numeric system cap are unresolved.
3. Pre-first-start external binding or exact transient internal VM allocation is
   unknown.
4. The version-specific update control, persisted disk-location source/key, default
   internal path, clean-stop method, placement commands, and first-party resources/
   endpoints are not established.
5. Because resolving those facts changes the plan, the blocked-design plan must be
   replaced and receive a new ID/SHA/current-turn authorization.
6. Diskutil UUID evidence must be linked to held mount identity and freshly rechecked
   when each guard is consumed.
7. Machine stop/open-file, settings/VM placement, default-internal inactivity, and
   reconnect evidence need version-specific commands and supervisor validation.
8. A typed rollback executor and authorized in-process writer-probe/seal driver remain
   required; standalone sealing is fail-closed.

B2b has no plan ID, hash, command, or authorization block. It remains a requirements
stub, and both SiRA conditions remain unauthorized.
The historical materialization loader/executor and the Docker image/fixture CLI paths
reject stale combined-B2 authority; historical JSON and commands remain only as
non-executable provenance.

## Ready-to-copy blocker-resolution block

There is no truthful ready-to-copy **installation authorization** while exact caps and
commands are unresolved. The only safe ready-to-copy block is therefore:

```text
I do not authorize execution of
PLAN-T07-GATE-B2A-DOCKER-STORAGE-QUALIFICATION-V1 or any Docker download,
installation, start, storage migration, or reconnect probe.

I authorize only a new read-only/source-verification design turn to resolve the exact
Mac mini operational-floor terms, current official Docker Desktop 4.85.0 build 235549
metadata, supported pre-first-start storage binding or transient internal allocation,
automatic-update suppression, persisted disk-location evidence source/key, default
internal disk path, clean-stop method, first-party endpoints/resources, held-descriptor
mount identity, machine reconnect/placement validation, typed rollback, and the
authorized writer-probe/seal driver.

That turn must produce a replacement executable Gate B2a plan with a new unique plan
ID and SHA-256, exact non-null internal floor/disk caps and placement commands, full
tests/review, and a new authorization packet. It must not download/install/start
Docker, pull/build an image, create a container, launch a browser, call an API, access
a secret, execute SiRA, modify scientific fields, or authorize B2b.
```

This block does not authorize Gate B2a. It makes the blocker-resolution scope explicit
without weakening the current prohibitions.

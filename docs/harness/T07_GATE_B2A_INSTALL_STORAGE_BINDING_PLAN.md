# T07 Gate B2a installation and storage-binding plan

Status: **blocked design; unauthorized and non-executable**

## Immutable identity

- Plan ID: `PLAN-T07-GATE-B2A-DOCKER-STORAGE-QUALIFICATION-V1`
- Plan path:
  `containers/sira-smoke/gate-b2a-install-storage-binding-plan.json`
- Plan SHA-256:
  `7ccd43e413ec8c4a21a4af043bef2477ede14b5bd40885c979cdeb7e48081eb1`
- Bound implementation commit:
  `321136b2a23158a7618e1489a4d2005d7f7ba1cd`
- Authorization placeholder: `AUTH-T07-GATE-B2A-PENDING`
- Authorization value in the plan: `false`

The JSON document is the exact machine-readable source for every ordered argument
array and per-action limit. It validates against
`schemas/docker-storage-qualification-plan.schema.json` and the semantic loader in
`src/giclab/harness/sira_storage.py`. It is not an executable authorization plan:
required system-cap and version-specific operations remain deliberately unresolved,
so a later resolved plan must receive a new ID, hash, and current-turn authorization.

## Scope and boundaries

The proposed Gate B2a sequence ends after Docker Desktop installation, external
disk-image binding, a stop/disconnect/reconnect/same-disk healthy-reopen check, final
stop, and B2a evidence sealing. It includes no image pull, image build, container,
Chromium/browser, SiRA dependency, model/provider/API request, real secret, SiRA
condition, cloud action, or scientific interpretation.

The exact external roles are:

- Docker disk image:
  `/Volumes/Macintosh HD - Data/GIC-Lab/t07/docker-desktop/disk-image`
- future build staging:
  `/Volumes/Macintosh HD - Data/GIC-Lab/t07/docker-build-staging`
- sealed artifacts:
  `/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts`

The exact Mac mini roles are:

- active attempts:
  `/Users/joseph/.local/share/gic-lab/t07-gate-b2a/attempts`
- B2a work/download/evidence:
  `/Users/joseph/.local/share/gic-lab/t07-gate-b2a`

## Ordered action contract

The plan contains 66 automatable child actions and 9 user-only actions, 75 total.
Twenty-four automatable actions are adjacent storage guards. Automatable actions
have exact argv arrays; user-only actions have instructions and no argv. The ordered
phases are:

1. Five repository identity/cleanliness/tree-binding checks, including the exact
   locked EXP-0001 science tree.
2. Three read-only external/APFS/system volume observations.
3. Ten fresh exact-root creation actions, each immediately preceded by its own typed
   guard.
4. Two bounded official metadata downloads and one exact metadata verifier.
5. One bounded DMG download and one exact size/SHA-256 verifier.
6. App-absence check, read-only DMG attach, exact `ditto` app installation, and detach.
7. Personal terms action, supported no-update action, automated guarded first start,
   installed version/build checks, and minimized Docker version/info/context capture.
8. User selection of the exact external directory, Apply/Restart, one cropped
   location-only image, and bound engine evidence.
9. User clean stop, pre-disconnect machine evidence, physical eject/disconnect,
   reconnect/remount/unlock, both-UUID guard, automated guarded restart, and
   same-engine reopen evidence.
10. User final stop and one-way 16,777,216-byte-capped evidence seal/copy.

Every failed action stops, every retry limit is zero, and identities are fresh. The
plan's blocking requirements and unresolved guard value deliberately prevent the
first storage mutation and everything after it from being authorized in its current
form.

## Exact aggregate limits

| Limit | Exact value | Mechanical state |
|---|---:|---|
| Aggregate wall | 7,200 s | Sum of per-step maxima is 6,240 s. |
| Aggregate captured output | 16,777,216 B | Sum of per-step maxima is 7,839,744 B. |
| Aggregate download | 577,786,748 B | 2,097,152 B appcast + 2,097,152 B checksums + 573,592,444 B DMG. |
| External incremental disk | 12,884,901,888 B | Exact safety ceiling; every external action also carries a per-action cap. |
| External retained-free floor | 200,048,192,717 B | Rechecked after every external write/VM action. |
| External pre-action free floor | 212,933,094,605 B | Retained floor plus aggregate external reservation. |
| Active attempts | 67,108,864 B | Mac mini only. |
| B2a evidence/sealed copy | 16,777,216 B | Local source retained after verified copy. |
| System incremental disk | **unresolved; null** | Blocking: no exact cap is invented. |
| API cost/tokens/model calls | USD 0 / 0 / 0 | No provider client/action. |
| Browser steps/screenshots | 0 experimental browser steps / 0 browser screenshots | One cropped Docker Settings image is a user GUI evidence action, not a browser action. |
| Automatable/user-only actions | 66 / 9 | Exactly 75 ordered actions; zero retry. |

Exact per-action wall, output, download, internal disk, and external disk values are in
the hashed JSON. A `null` internal value is not unbounded permission; it is a hard
authorization blocker.

## User-only actions

The user alone must personally accept terms; establish the version-specific supported
no-update setting; select the external disk location; Apply/Restart; permit the
cropped settings image; Quit before disconnect; eject/disconnect;
reconnect/remount/unlock; and Quit finally. The two standalone Docker starts are exact
automatable `/usr/bin/open -na /Applications/Docker.app` arrays immediately after
typed guards. User attestations record only the exact action and timestamp. They never
prove machine placement or permit Codex to accept terms.

## Reconnect proof

Before disconnect, Docker must be stopped and no process may have the exact external
VM file open. After physical reconnect, the control plane resolves the volume again
without pinning a device number, matches both approved UUIDs, rechecks APFS/writable/
unlocked/UTDM state, exact paths, free-space floors, and the external disk file
identity, then consumes a new guard before restart. The restarted engine must reopen
the same external disk, retain the same engine/context identity, report healthy, and
leave the version-specific default internal disk absent/inactive. Docker is stopped
again before sealing. A skip, replay, mismatch, or stale observation blocks B2b.

Those are replacement-plan requirements, not current proofs. The V1 state machine
does not yet bind machine-verifiable stopped/open-file evidence to its stop states,
does not re-observe the mount identity at guard consumption, and does not semantically
validate version-specific placement outputs. Those gaps are explicit blockers.

## Stop and cleanup

Failure authorizes no retry. The plan declares one clean detach of `/Volumes/Docker`
when mounted and a verified user Quit when Docker is running. Docker is not
automatically uninstalled; no default internal VM file, external Docker state, user
file, failed staging tree, DMG, or local evidence may be deleted. The sealed local
source and verified external copy must both be retained. A future executable driver
must implement this as typed fail-state behavior; the current loader preserves the
hashed prose but does not execute rollback, which is authorization-blocking.

## Blocking facts

1. Official artifact metadata is retained but not current-reverified under this
   turn's no-network rule.
2. Six system-floor terms are unknown, so the numeric system floor and aggregate
   internal disk cap are null.
3. Pre-first-start external binding or an exact transient internal-VM bound is not
   sourced.
4. Supported update suppression, persisted location key/source, default internal
   path, clean-stop method, and placement commands are not version-verified.
5. Docker Desktop's own unavoidable startup endpoints/resources cannot yet be exactly
   classified.
6. Fresh UUID evidence is not yet linked to a held mount descriptor and re-observed
   when a storage guard is consumed.
7. Machine stopped/open-file, settings/VM placement, default-internal inactivity, and
   reconnect evidence are not wired into supervisor completion.
8. Typed rollback and the authorized in-process writer-closure/seal driver do not yet
   exist; the standalone seal-and-copy CLI is deliberately disabled.

The historical combined Gate B2 plan and SHA-256
`10fd0350c5e14c4c6d4e32bf40f1f9f696735eae81815a00cd8032e652beaa25`
remain superseded.

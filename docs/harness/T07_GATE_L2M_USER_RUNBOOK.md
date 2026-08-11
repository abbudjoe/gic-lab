# T07 Gate L2M user runbook

Status: **historical V3 runbook; blocked and superseded; do not execute**

Gate L2M.1 burned V3/run 0003 after a safe pre-mutation stop. The retained global
firewall projection cannot prove exact restoration because the provider response and
unknown raw-key structure were not retained. Every manual step below is therefore
historical only. The next possible action is a separately authorized one-GET baseline
capture under
`docs/harness/T07_GATE_L2M_FIREWALL_BASELINE_CAPTURE_AUTHORIZATION_PACKET.md`.
There is no current manual-console qualification plan or authorization.

This runbook preserves the human side of historical plan
`PLAN-T07-GATE-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-V3`, run
`RUN-T07-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-0003`. The plan is 21,641 bytes,
SHA-256 `1931fcacda4194063c0116ff9630d82f3b8f4ec07ff9b0310342335db629f654`,
and all authority fields are false. Do not open the Lambda console, start the
observer, use the credential, mutate a firewall/ruleset, launch an instance, open
Jupyter, pull an image or run a container until the user supplies a fresh exact
authorization in a later turn.

The supervisor must start no later than `2026-08-12T05:15:19.646016Z`. If that time
has passed, stop: the public metadata/bundle freshness contract requires a new plan,
review and authorization.

## Actors and non-negotiable order

- `user`: the only actor permitted to use the Lambda console or interact with
  Jupyter; every mutation is manual.
- `observer`: GET-only Lambda observations plus local checkpoint, evidence and
  archive validation; it has no mutation method.
- `host-bundle`: one deterministic qualification command inside Jupyter.

The plan has exactly 23 ordered steps:

1. Observer preflight and read-only revalidation.
2. User launch-wizard offeredness check without launch.
3. Observer seal of the exact original global firewall.
4. User replacement of global firewall with private TCP/22 `/32` only.
5. Observer exact global-restriction verification.
6. User creation of the owned regional ruleset.
7. Observer bind and exact semantic verification of that ruleset.
8. User selection of the exact launch configuration without launch.
9. Observer durable launch-window arming.
10. User clicks Launch exactly once.
11. Observer binds exactly one instance or enters incident.
12. User opens Cloud IDE/Jupyter for the bound instance.
13. User uploads the exact qualification bundle.
14. User runs the hash-first qualification once.
15. User downloads evidence to the exact inbound root.
16. Observer validates archive and host/container evidence.
17. User terminates only the bound or authorized incident-scope instances.
18. Observer proves the authorized scope terminal or absent.
19. User deletes the owned regional ruleset.
20. Observer proves the owned ruleset absent.
21. User restores the exact sealed original global firewall.
22. Observer proves exact semantic restoration.
23. Observer seals evidence and copies it one-way to the approved archive.

No step may be reordered or skipped on the normal path. Incident paths may omit only
an inapplicable user action, such as a termination attestation when the bounded
post-launch observations prove that no instance exists; they never fabricate a
checkpoint.

## Starting the future observer

Run from the canonical clean repository root. The authorized command is the plan's
exact shell-free array, with the future authorization supplying the final clean
commit, authorization reference/hash and the already-fixed plan hash:

```text
.venv/bin/python
-I
containers/sira-smoke/lambda/manual-console/l23_supervisor_bootstrap.py
--repository-root
.
--plan
containers/sira-smoke/lambda/manual-console/gate-l2m-host-qualification-plan-v3.json
--plan-sha256
1931fcacda4194063c0116ff9630d82f3b8f4ec07ff9b0310342335db629f654
--expected-commit
<EXACT-FINAL-CLEAN-GATE-L2-3-HANDOFF-COMMIT>
--authorization-reference
<FRESH-AUTHORIZATION-REFERENCE>
--authorization-sha256
<SHA256-OF-THE-FRESH-USER-AUTHORIZATION-TEXT>
```

The isolated bootstrap validates exact repository source, plan/artifact hashes,
branch/commit/cleanliness, private seals, the unique SSH-key name plus sealed provider
identity and recomputed local public-key fingerprint, run-root freshness, storage
identity/floors, public-metadata age and all caps before it may read
`LAMBDA_API_KEY`. It uses only the in-process HTTPS GET transport. It never invokes
curl, wget, shell HTTP, SSH, a browser controller or an automated mutation.

Do not paste the credential or any private checkpoint content into chat. The future
supervisor may receive only `LAMBDA_API_KEY` through the approved nonlogging local
secret channel. `SIRA_API_KEY` and `OPENAI_API_KEY` are out of scope.

## The 13 user checkpoints

The observer issues one private challenge at a time and prints only its checkpoint
type. Each checkpoint is a fresh, current-user-owned, single-link regular file at mode
`0600`, at most 16,384 bytes, created under the observer's held private checkpoint
root within the issued 300-second window. Copy the matching inert template from
`containers/sira-smoke/lambda/manual-console/checkpoints/`, fill only the private
challenge values locally, and never reuse a file, nonce or identity. Do not add a raw
provider ID, IPv4, fingerprint, Jupyter URL/token, secret or private path.

Instance binding and terminal/absence proof are observer-only durable receipts. The
user does not create `instance_bound` or `instance_terminal_verified` files.

### Exact user actions

1. **`launch_wizard_image_offered`** — Open the launch wizard, select
   `gpu_1x_a10` and `us-east-1`, confirm `img-0032` / Lambda Stack 22.04 /
   `22.4.5-2141` is offered, do not click Launch, then write checkpoint 01. If it is
   absent, close the wizard and stop before every mutation; never substitute another
   image.
2. **`global_firewall_restricted`** — Only after the observer has passed preflight
   and sealed the fresh original globals, replace the global rules with exactly one
   custom TCP rule for port 22 from the privately bound current `/32`. Submit once,
   write checkpoint 02, and wait for exact read-only verification.
3. **`regional_ruleset_created`** — Create exactly one `us-east-1` ruleset using the
   private run-owned name and the same sole TCP/22 private `/32` rule. Write checkpoint
   03 and wait while the observer binds exactly one private ID and verifies equality.
4. **`launch_configuration_selected`** — In the wizard select exactly
   `gpu_1x_a10`, `us-east-1`, `img-0032` / `22.4.5-2141`, no filesystem,
   `fractal-lambda-codex`, and the newly bound regional ruleset. Do not launch. Put
   the observer-supplied configuration hash in checkpoint 04.
5. **`launch_clicked_once`** — Wait for the observer's durable launch-window-armed
   receipt. Recheck every selection, click Launch exactly once, and write checkpoint
   05 with the same configuration hash and offeredness attestation. Never click again,
   even after an ambiguous outcome.
6. **`cloud_ide_opened`** — Proceed only after the observer durably binds exactly one
   matching instance. Open Cloud IDE/Jupyter for that instance under the already
   strict firewall, then write checkpoint 06. If it does not work, do not open a port
   and do not use SSH; enter cleanup.
7. **`qualification_bundle_uploaded`** — Upload exactly the files bound by
   `containers/sira-smoke/lambda/manual-console/manifest.json` into the approved
   Jupyter bundle directory, without editing or adding a file. Write checkpoint 07
   with the fixed manifest hash.
8. **`qualification_command_started`** — Run only the plan's exact hash-first
   `qualification_bootstrap_argv` once. It starts `/usr/bin/python3 -I -S -c`, verifies
   `qualification_driver.py` SHA-256
   `ab9a3f8981d2e60ea5b57bb7cf63512f64cdb89f26d8183788aedc2dbe4b5050`
   before execution, and uses the private instance binding supplied by the observer.
   Direct driver execution is forbidden. Write checkpoint 08 immediately after the
   one start.
9. **`qualification_command_completed`** — Wait at most 300 seconds for the single
   typed success/failure line. Write checkpoint 09 when it appears. Do not repair,
   install, retry or rerun. Timeout or an unavailable evidence archive enters cleanup.
10. **`qualification_bundle_downloaded`** — Download the one named success or failure
    evidence ZIP through Jupyter into the exact fresh Mac mini inbound root. Do not
    rename, unpack or edit it. Compute its SHA-256 locally, place that digest in
    checkpoint 10, then let the observer bind the already-written checkpoint to the
    exact held archive bytes and validate them. A valid failure archive remains a
    failure and goes directly to cleanup; it never permits a rerun or Gate L3.
11. **`termination_confirmed_by_user`** — On the normal path terminate only the exact
    bound instance using the provider confirmation phrase `erase data on instance`.
    In a multiple-match incident, terminate every private instance ID that the
    observer proves is attached to the unique owned ruleset. Write checkpoint 11 only
    after all authorized termination clicks. If two bounded observations prove a
    true zero-instance outcome, do not make a false termination checkpoint.
12. **`regional_ruleset_deleted`** — Only after the observer has durably proved the
    authorized instance scope terminal/absent, delete exactly the owned regional
    ruleset. Write checkpoint 12 and wait for read-only absence proof.
13. **`global_firewall_restored`** — Only after terminal/absence and ruleset absence
    are durable, restore the exact sealed original global rules. Put the
    observer-supplied semantic hash in checkpoint 13. Wait for exact verification and
    external evidence sealing before considering the gate closed.

## Qualification limits

The host bundle may make at most 32 Docker calls: 22 ordinary and ten
cleanup-reserved. Each call is capped at 1,048,576 output bytes; aggregate output is
8,388,608 bytes, partitioned into 7,340,032 ordinary and 1,048,576 cleanup-reserved.
It may create one container, use five outcome-unknown identity polls plus three stable
absence observations one second apart, run the adversarial fixture for 30 seconds,
spend 270 seconds on ordinary Docker work, and spend at most 300 seconds including
cleanup. It uses a 2,211,507-byte compressed layer for
the immutable public BusyBox identity recorded in the bound source observation,
`linux/amd64`, `--pull=never` at create, no network, a read-only root, private PID/IPC,
`cap-drop=ALL`, no-new-privileges, 1 CPU, 536,870,912-byte memory/swap, 64 PIDs,
16,777,216 bytes each for `/tmp`, `/run` and shm, one 1,048,576-byte local log,
restart `no`, and lifecycle control by immutable container ID. It performs no install,
runtime update, browser, model or SiRA action.

The observer may make 44 GETs total, each at most 1,048,576 bytes and at least one
second apart, with 16,777,216 aggregate response bytes and the same exact 44-file /
1,048,576-byte-each / 16,777,216-byte-aggregate private-observation envelope, no
retry, pagination or redirect follow. Phase limits are 6 preflight, 1 original-global seal, 1 strict-global
verification, 1 ruleset bind, 9 instance bind, 0 Cloud IDE, 0 qualification, 10
termination, 2 ruleset absence, 1 global restoration and 13 incident. It has 512
events, 4,096 bytes per event, a 2,097,152-byte journal, 16 bounded local process
calls and 4,194,304 local process-output bytes. Each request has 60 seconds. Observer
active wall is 6,000 seconds: 1,200 prelaunch, 3,600 provider and 1,200 post-provider
cleanup; archive is 300 seconds and total wall 6,300 seconds. Phase deadlines are 600
seconds launch-to-active, 600 Cloud IDE, 300 qualification, 300 download-validation,
1,800 normal termination click, 600 terminal verification, 300 firewall cleanup and
900 incident headroom.

Each remote source and archive set is capped at 16,777,216 bytes. Same-attempt remote
retention is capped at 34,603,008 source bytes, 33,554,432 archive bytes and
68,157,440 aggregate bytes. Local source and sealed evidence are each capped at
41,943,040 bytes; Mac active evidence is capped at 83,886,080 bytes and the external
sealed archive at 41,943,040 bytes.

Provider limits are one normal instance, one human Launch click, zero persistent
filesystems, USD 2.00 and 3,600 seconds. Automated cloud mutations, SSH, model calls,
model tokens, browser automation and SiRA executions are all zero.

## Incident and abort contract

- Image not offered or pre-mutation price/capacity/image/key/firewall/zero-instance
  drift: stop before mutation.
- Global or regional restriction mismatch: perform no launch; retain exact evidence
  and use only the ordered user cleanup path that is already applicable.
- Zero, multiple or semantic-drift launch observation: run no workload and never make
  a second launch click.
- Multiple matches: cleanup authority covers only private IDs attached to the owned
  ruleset. An unattached or otherwise unbound account row is not inferred to be T07;
  preserve the strict firewall and stop for a new private human decision rather than
  broadening termination authority.
- Cloud IDE failure: open no port, use no SSH, terminate and clean up.
- Upload, qualification or evidence failure: never rerun; terminate and clean up.
  Preserve an exact failure archive or any partial retained bytes when available.
- Termination unavailable, nonterminal by deadline, ruleset deletion failure, global
  restoration failure or Lambda control-plane outage: preserve strict firewall and
  all evidence, launch nothing else, record residual billing exposure, and wait for a
  separately authorized recovery decision. Never broadly delete/prune account state.
- Archive unavailable: preserve the local source; do not use internal fallback or
  treat the gate as eligible.
- Observer exit/crash/restart after live work permanently burns this run identity.
  Preserve the ledger prefix; user cleanup remains manual, and later observation/
  sealing requires a new reviewed recovery run and authorization.

The normal user termination click is due no later than 1,800 seconds after Launch;
terminal proof has up to 600 seconds and firewall cleanup 300 seconds, all within the
3,600-second provider hard wall. A provider/control-plane outage can exceed both wall
and USD 2.00 despite local enforcement; that acknowledged residual risk never permits
a replacement launch.

## Completion boundary

Success requires a complete schema-valid observer journal, all applicable single-use
checkpoints, exact host/container evidence, provider terminal/absence proof, owned
ruleset absence, exact global restoration, bounded local seals, one-way copy to APFS
UUID `8478609D-FA37-4ED5-875D-47AE912B9151` on physical store
`7904A6F1-F483-4ED7-9E34-BFECAB31C63E`, destination hash verification, fsync,
atomic finalize, retained local source and no internal fallback.

Gate L2M success is infrastructure evidence only. It authorizes neither Gate L3 nor
Gate L4, neither SiRA condition, no model call and no scientific interpretation.

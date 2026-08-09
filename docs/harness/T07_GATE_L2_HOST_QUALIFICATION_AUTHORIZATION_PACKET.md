# T07 Gate L2 Lambda host qualification packet

Status: **design complete; unauthorized; non-account-bound; non-executable until an
authorized Gate L1 succeeds**

This is a requirements packet, not a launch plan. It deliberately has no Gate L2 plan
ID/hash, authorization reference, account/workspace binding, instance type, region,
provider image ID, SSH key, firewall ruleset, launch request, instance ID, or ready
authorization block. Inventing any of those values would violate Gate L0. The packet
must be regenerated after L1 and a fresh user decision.

Future success evidence must validate against
`schemas/t07-lambda-host-qualification.schema.json` (SHA-256
`704d780acc7669025ca2ac8b41a1ad70446a0641688a151fecd0e8d18adc427a`). Any failed, partial, ambiguous-launch, secret-loss,
termination-unconfirmed, or open-billing outcome must instead validate against
`schemas/t07-lambda-host-qualification-incident.schema.json` (SHA-256
`21c6402e38414dad1ba1f6dc17c5967d049654a83238a85a4f9c565d2afe0c1d`). Mock/schema tests prove only the control-plane
contract, never kernel containment or provider termination.

## Entry conditions

Before a Gate L2 plan can exist, all of the following must be met:

1. An explicitly authorized Gate L1 run produces a schema-valid, bounded, redacted
   inventory with path, bytes, SHA-256, observation time, account/workspace hashes, and
   exact selected type/region/image/price; the inventory and copy record must also be
   sealed and hash-verified at the approved MacBook archive. An unarchived L1 artifact
   is not consumable by L2.
2. The user approves exactly one existing SSH key ID/name and one existing eligible
   regional TCP/22-only firewall ruleset ID after reviewing its source CIDR. The
   effective global ruleset must also contain only TCP/22 allow rules.
3. The user supplies the matching local SSH identity through an outside-repository
   secret channel. Gate L0 did not access or inspect a private key or agent.
4. A source-backed or separately user-approved server-host-key fingerprint establishes
   first-contact trust in a fresh per-attempt `known_hosts` file. `ssh-keyscan` alone is
   discovery, not authentication; global `known_hosts` and SSH-agent state may not be
   mutated. Lambda's reviewed public API currently supplies no attested ephemeral host
   key, so this is an unresolved material blocker.
5. The exact type remains available in the exact region at the same or lower price;
   the exact x86_64 `gpu-base-22-04` image ID remains available; no duplicate T07
   instance exists; and all pre-existing instances are recorded as unrelated.
6. A new clean commit-bound plan renders the exact launch/termination/API/SSH/Docker
   arrays, caps, evidence paths, authorization reference, and hard monotonic deadline.
7. The user separately authorizes that exact plan, at most USD 2.00 provider compute,
   and termination retries for the single minted instance ID.

The future launch may atomically attach only the exact T07 ownership/authorization
tags rendered by the reviewed plan to the newly minted instance. It may not add,
change, or remove tags on any pre-existing account resource.

Gate L1 authority never implies Gate L2 authority.

## Intended future actor and lifecycle

The future operational actor is Codex configured to GPT-5.6 Luna/max under the exact
Gate L2 authorization. Sol remains the scientific-design and post-run review owner.
The actor may not leave an instance running for user inspection.

```text
mint absolute 3,600-second aggregate monotonic deadline
  -> preflight/revalidate with one-second provider-request pacing
  -> record the launch checkpoint immediately before POST without extending the aggregate deadline
  -> launch exactly one instance, no persistent filesystem
  -> capture immutable provider instance ID immediately
  -> wait boundedly for active and SSH
  -> capture host/runtime evidence without mutation
  -> pull one pinned tiny image
  -> run one no-network containment fixture
  -> remove owned test resources and prove zero residue
  -> copy/hash/verify evidence to Mac mini
  -> provider-API terminate the exact minted ID
  -> poll terminal/nonbillable
  -> record actual duration/list-cost estimate
  -> seal/copy evidence one-way to approved MacBook archive
  -> stop
```

The conservative aggregate deadline is minted before the first L2 provider request,
so every request and every pacing delay consumes the same 3,600-second budget. An
additional launch checkpoint is recorded immediately before the launch POST, before
any response latency or provider billing-state ambiguity, and it may never reset or
extend the aggregate deadline. Request-start and provider-active times are recorded
separately. A `finally`
termination path is armed when the POST is sent, not only after a response ID arrives.
Test or evidence-copy failure cannot pause billing for review. Termination may be
attempted at most three times against the same immutable ID (initial request plus two
bounded safety retries for timeout/5xx); launch has zero retries.

If the launch response is lost or lacks an ID, exactly one reserved recovery GET is
used. It compares the prelaunch instance-ID set with exact name
`giclab-t07-l2-qualification` and exact experiment/gate/authorization tags. Exactly one
new match becomes the sole immutable termination target. Zero or multiple matches
forbid broad/name-based termination and create an open billing incident requiring a
new user action. If provider termination cannot be confirmed before call/wall caps,
automatic calls stop, the exact incident schema is sealed, and new authority is
required; the gate is never reported complete.

Host `shutdown`, `poweroff`, restart, suspend, rebuild, or delete-by-name are forbidden.
Only Lambda's terminate endpoint for the exact minted ID ends billing authority.

## Future exact provider and network surface

The final plan must use API base `https://cloud.lambda.ai` and OpenAPI 1.10.0 SHA-256
`365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded`.
It may contact only:

- `cloud.lambda.ai:443` for bounded inventory revalidation, one launch, immutable-ID
  status polling, termination, and terminal polling;
- the launched instance's exact L1/L2-bound public endpoint on TCP/22 for SSH and
  evidence transfer;
- `auth.docker.io:443` and `registry-1.docker.io:443` for the one qualification-image
  token/manifest/config/layer pull;
- a registry blob redirect under `production.cloudflare.docker.com:443` only if the
  exact Docker registry response supplies it and the digest/byte caps remain enforced.

No apt, OS/package/runtime update, GitHub, PyPI, uv, MCR, Playwright, OpenAI, live
website, Jupyter, telemetry, or arbitrary egress is allowed. The fixture container's
network is exactly `none`. Host egress needed for provider control occurs from the Mac
mini; only the one Docker image pull occurs from the instance.

## Numeric Gate L2 caps

These are maximum design values. L1 must replace the list-price term with the selected
integer cents/hour before authorization.

| Resource | Aggregate cap | Per-operation cap |
|---|---:|---:|
| Provider billing wall | 3,600 s | hard monotonic deadline minted immediately before launch POST through terminal confirmation |
| Provider compute hard ceiling | 200 cents including tax/metering reserve | selected one-hour list price must be <=150 cents; exact list-price cap is selected integer cents/hour |
| Lambda persistent filesystem | 0 attached; 0 cents | both `file_system_names` and `file_system_mounts` exact empty arrays |
| Launch targets/requests/retries | 1 instance; 1 request; 0 retries | no batch/quantity field |
| Termination targets/requests | 1 exact minted ID; at most 3 requests | initial plus at most 2 safety retries; no unrelated ID |
| Provider API requests | at most 134 | 8 revalidation GET + 60 active polls + 1 ambiguity-recovery GET + 1 launch POST + 3 termination POST + 60 terminal polls + 1 final GET |
| Provider request pacing/retry | >=1 monotonic second between every request start; 0 automatic transport retries | all pacing delay counts inside the single 3,600-second aggregate deadline; termination's at-most-two safety retries are explicit lifecycle requests, not transport retries |
| Provider API response bytes | 16,777,216 B | 1,048,576 B per response; streaming abort before retention/parse overrun |
| SSH readiness attempts | 30 | 10-second spacing; 300-second aggregate |
| Successful SSH control sessions | 2 | one bounded evidence/control session and one bounded hash-verified transfer session |
| Remote host command invocations | 48 | 1,048,576 B stdout+stderr per call; 16,777,216 B aggregate |
| Docker CLI calls | 32 | 1,048,576 B stdout+stderr per call; 16,777,216 B aggregate; one pull/create/start only |
| Qualification-image registry bytes | 8,388,608 B | known layer 2,211,507 B; manifests/config plus redirect overhead within aggregate |
| Incremental Docker image/layer disk | 67,108,864 B | pre/post observed; cap exceed stops and terminates |
| Container CPU | 1.000 CPU | one fixture container |
| Container memory plus swap | 134,217,728 B | memory and memory-swap equal; no additional swap |
| Container PIDs | 64 | cgroup-enforced |
| Fixture wall | 30 s | includes process evidence, TERM, and KILL escalation |
| Fixture stdout/stderr/log | 1,048,576 B | local Docker log driver max-size 1m, max-file 1 |
| Container tmpfs | 20,971,520 B total | `/tmp` 16,777,216 B; `/run` 4,194,304 B |
| Private shm | 16,777,216 B | no host IPC |
| Remote qualification evidence | 67,108,864 B | regular files only; no symlink/nonregular entry |
| SSH/rsync transfer | 67,108,864 B | one source-to-Mac-mini copy, source retained until hash match |
| Mac mini active evidence | 67,108,864 B | bounded ignored `artifacts/t07/lambda/gate-l2/<attempt-id>` root |
| Durable sealed copy | 67,108,864 B | one-way to approved MacBook archive after source seal and volume guard |
| Experimental model/API cost | USD 0.00 | no OpenAI/provider-model calls |
| Experimental model tokens/calls | 0 / 0 | no OpenAI client; operational Codex is outside experiment accounting |
| Browser actions/screenshots | 0 / 0 | no Chromium/Playwright |
| SiRA executions | 0 | neither condition |

The 200-cent hard budget is the user's aggregate authorization ceiling. Lambda's
published price excludes applicable sales tax, so the exact enforceable metered
list-price cap is the inventory-selected cents/hour and the 200-cent ceiling includes
the remaining reserve. L2 must stop before launch if the selected list price exceeds
150 cents/hour or a current account-specific charge would make the 200-cent ceiling
unreliable.

All three raw-output counters are recorded in both success and incident evidence:
provider API response bytes, SSH command stdout+stderr bytes, and Docker stdout+stderr
bytes. Hitting a per-call or aggregate ceiling closes the stream, stops new workload
actions, preserves bounded incident evidence, and proceeds to provider termination.
The 67,108,864-byte retained-evidence cap does not substitute for these pre-redaction
read/hold limits.

Both success and incident evidence also record the monotonic provider-request start
count, minimum observed inter-start spacing in milliseconds, spacing-violation count,
aggregate-deadline-before-first-request proof, and proof that the launch checkpoint
did not extend that deadline. Success requires at least 1,000 ms minimum spacing and
zero violations. Incident evidence may truthfully retain a pacing violation, but a
violation stops new workload actions and proceeds to bounded termination; it never
authorizes a compensating retry.

## Lambda control-secret and SSH trust contracts

The future provider control secret is exactly `LAMBDA_API_KEY`, supplied outside Git
through a nonlogging supervisor secret channel. The supervisor holds it only in memory
through provider terminal/nonbillable confirmation and constructs Authorization
headers internally. It never appears in argv, URL, path, label, log, evidence, hash,
filesystem, Docker configuration, or exception. `SIRA_API_KEY` and `OPENAI_API_KEY`
remain forbidden fallbacks and unread. If this control secret becomes unavailable or
invalid after the launch POST, all workload/SSH/Docker activity stops; host shutdown
is not substituted for provider termination; the immutable instance ID or ambiguity
facts are retained; a billing incident stays open; and the operator requests immediate
secret restoration/new user authority.

The client private SSH identity is a separate outside-repository secret. The final
plan must bind its exact approved handle without copying key material into evidence.
Server identity requires an exact algorithm and `SHA256:` fingerprint in a fresh
attempt-owned `known_hosts` file, with strict checking and no global/agent mutation.
No official source reviewed in L0 establishes an attested per-instance host key, so L2
cannot be materialized until that bootstrap is separately source-verified or expressly
authorized by the user. Accepting unauthenticated `ssh-keyscan` output is forbidden.

## Host qualification evidence

The final plan must revalidate all selected account bindings immediately before launch
and then capture, without package or configuration mutation:

- exact provider instance record, ID, state transitions, price, type, region, image
  ID/name/family/version/architecture, key name/ID, ruleset ID and empty filesystem
  lists;
- `/etc/os-release`, kernel and `uname -m` (must be x86_64), cgroup version/mounts and
  Docker cgroup driver;
- Docker client/server versions and full version JSON, daemon root/storage/logging
  driver, containerd, runc, BuildKit/buildx if already present, and relevant systemd
  unit status;
- root-filesystem capacity/free bytes and Docker root capacity/free bytes;
- all pre-existing container IDs, image IDs, networks and volumes before the pull, so
  unrelated state is never removed;
- all post-probe owned IDs, lifecycle snapshots, process evidence, logs, resource
  deltas, and zero-residue scans.

Missing provider Docker, architecture drift, host mutation need, cgroup/private
namespace failure, insufficient disk, nonempty unexpected pre-existing T07 state, or
unbounded logging is a failed qualification followed by evidence capture and provider
termination. No `apt update`, `apt upgrade`, runtime service edit/restart, group edit,
daemon JSON edit, kernel/sysctl change, or package install is permitted.

## Immutable qualification image

The only permitted workload image is the Docker Official Image:

```text
busybox@sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0
```

The digest is the exact linux/amd64 platform manifest, not a tag and not merely the
multi-platform index.

| Identity | Exact value |
|---|---|
| Metadata-resolution tag only | `busybox:1.37.0-glibc` |
| Multi-platform index | `sha256:4279d9b47df4c1b02d80efd8d02cd59b3a8182c1e785a4ff3f6983bee19dc8b0`, 8,861 B |
| linux/amd64 manifest | `sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0`, 610 B |
| Config | `sha256:db287cb6be81219cd18c1d82b70908f5d33eb028568b456f78eedff2ff2930e4`, 459 B, linux/amd64 |
| Compressed layer | `sha256:436a1b1fd078ee8e117111472724c2827077657189af7a781829d0825d48d2ab`, 2,211,507 B |
| Rootfs diff ID | `sha256:412f8a616e1efb03d4ab94ce18ebddf3f068b637f1c7ae8dbc82306a852de408` |
| Image creation | 2024-09-26T21:31:42Z |
| Source | signed official-images commit `01fdecf62623f274c7043f3d331512bd0fd1e2cf`; busybox source commit `e7bf068f570ae5a3236675c3c6b22a576773e833`; amd64 distribution commit `70ce0fb98bee360bbcce132660d727bf6ce55a99` |
| Licenses | Apache-2.0 packaging; GPL-2.0 BusyBox program |

After immutable-image inspection, the single fixture container's entrypoint first runs
bounded `busybox --list` validation for `sh`, `setsid`, `sleep`, `ps`, and `kill`, emits
the fixed marker `T07_APPLETS_VERIFIED=sh,setsid,sleep,ps,kill`, and only then starts
the adversarial spawn sequence. This is one container, not an applet-check container
plus a probe container. Missing applets fail qualification. There is no floating-tag
fallback.

## Container control contract

The final plan must render exact argument arrays after the Docker executable and host
identities are observed. The create policy is invariant:

- platform `linux/amd64`; image by platform-manifest digest above; one fresh exact
  attempt/container name and labels binding experiment `EXP-0001`, gate `T07-L2`,
  authorization, repository commit, provider instance ID, fixture SHA, and attempt ID;
- omit Docker `--pid` so inspect `PidMode` must be empty/private; explicit
  `--cgroupns private`, `--ipc private`, `--network none`;
- `--privileged=false`, no host namespace, no runtime socket/device/host mount,
  `--cap-drop ALL`, no capability add, `--security-opt no-new-privileges:true`,
  `--read-only`, `--init`, restart `no`;
- CPU 1.0, memory 134,217,728 B, memory-swap 134,217,728 B, PIDs 64, shm
  16,777,216 B, `/tmp` tmpfs 16,777,216 B, `/run` tmpfs 4,194,304 B;
- local log driver, `max-size=1m`, `max-file=1`, stop timeout 5 seconds;
- byte-exact fixture file
  `containers/sira-smoke/lambda/adversarial-containment.sh`, 1,384 B, SHA-256
  `09838913b14d23da939225cb89411619e91cb9ee023a2721b5b7c3890ac90aea`,
  supplied as one nonsecret command argument only after local/remote hash verification;
  no mutable host bind mount.

The fixture ignores TERM, creates children/grandchildren and a new session, reparents
a grandchild, and continues spawn attempts until the cgroup PID cap prevents more.
Because the container may fill its PID quota, pre-stop evidence cannot depend on
`docker exec`. The supervisor uses daemon-side `docker top`, immutable inspect, and the
fixture's bounded log/markers; `container_exec_calls` is exactly zero. It records the
immutable container ID, issues bounded stop, proves TERM was ignored, escalates to
KILL, records terminal inspect/log/evidence, removes by exact ID, and proves no owned
labeled container, process, network, volume, tmpfs, or auxiliary resource remains. It
never uses host process-group enumeration as the containment handle.

Mock tests validate only this control plane. Gate L2 must empirically establish the
kernel/runtime behavior.

## Evidence transfer, sealing, and cleanup

The instance owns a fresh mode-restricted nonsecret qualification root. On any failure,
the operator first closes writers and creates a regular-file manifest with sizes and
SHA-256 values, then transfers at most 67,108,864 bytes to the bounded Mac mini
attempt root through the exact approved SSH identity. macOS `/usr/bin/ssh` reports
OpenSSH 10.2p1/LibreSSL 3.3.6 and `/usr/bin/rsync` is openrsync protocol 29; final
arrays and identity path/agent binding remain L1/L2 inputs.

The remote source stays intact until the Mac mini recomputes every hash. Evidence-copy
failure does not postpone provider termination: terminate first, retain whatever local
and remote manifest evidence was obtained, and report the incomplete transfer.

After terminal provider confirmation, the Mac mini source is fsynced, symlink and
nonregular entries are rejected, every file is hashed, and the tree is sealed. A
one-way copy may then target the D-018 archive
`/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts` only after fresh UUID,
physical-store, APFS/UTDM, writable/unlocked, no-symlink, free-floor, and held-descriptor
guards. Destination hashes and fsync/atomic finalization are mandatory; live
bidirectional synchronization is forbidden. The Mac mini source remains until
independent archive verification.

Cleanup targets only the exact container ID, fresh attempt root, and minted provider
instance ID. Docker system prune, image prune, network prune, volume prune, unrelated
container/image removal, broad process killing, filesystem mutation, prior evidence
deletion, and account-resource mutation are prohibited. The pulled qualification
image may be left only long enough to record post-state; because the host is then
terminated, no provider resource survives.

## Gate L2 stop boundary and blockers

Successful qualification ends after evidence sealing and confirmed provider
termination. It does not pull the Playwright image, build SiRA, use a dummy or real
`SIRA_API_KEY`, open Chromium, contact OpenAI, or execute reactive/simulative. The
provider-control `LAMBDA_API_KEY` is required only for the lifecycle described above.

Current blockers are exactly the missing hash-verified archived L1 artifact and its
current account facts, user-approved existing key/ruleset bindings, local SSH client
identity handle, unresolved authenticated server-host-key bootstrap, regenerated
clean-commit-bound L2 plan/hash, availability of `LAMBDA_API_KEY` through terminal
confirmation, and fresh L2 authorization. Because those values are unknown, there is
no ready-to-copy Gate L2 authorization block in this packet.

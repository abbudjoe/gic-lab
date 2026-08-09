# T07 Gate L1 read-only inventory authorization packet

Status: **ready for a separate user decision; unauthorized; do not run from this
packet alone**

This packet grants no authority. A future authorization may cover only eight Lambda
account GETs and the bounded local sealing/copy actions below. It cannot authorize a
launch, paid compute, SSH, container, browser, model request, SiRA, or Gate L2.

## Exact identity

| Field | Exact value |
|---|---|
| Provider / API base | Lambda On-Demand Cloud / `https://cloud.lambda.ai` |
| Public API lock | OpenAPI 1.10.0; SHA-256 `365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded` |
| Plan ID | `PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V1` |
| Run ID | `RUN-T07-L1-LAMBDA-INVENTORY-0001` |
| Plan path | `containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan.json` |
| Plan SHA-256 / bytes | `c7151737bd029e3ebad45d59dc2d9fcd58f401dc7d8658021f1d384129555c69` / 3,562 B |
| Redacted artifact | `artifacts/t07/lambda/gate-l1/inventory-redacted.json` |
| Local verification record | `artifacts/t07/lambda/gate-l1/inventory-copy-record.json` |
| Durable archive | `/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts/RUN-T07-L1-LAMBDA-INVENTORY-0001` |
| Inventory schema | `schemas/t07-lambda-inventory.schema.json`; SHA-256 `180c634365edc83ebb8f3a9173a1856a00d0758e352e45439c67106f1763261e` |
| Supervisor | `src/giclab/harness/lambda_inventory.py` and `src/giclab/harness/lambda_archive.py` |
| Future actor | Codex operator configured to GPT-5.6 Luna/max |

Because a commit cannot contain its own SHA, the future command must bind the exact
clean `phase-1/sira-smoke-lambda` Gate L0 commit reported in the final handoff. Branch,
commit, clean-tree, plan hash, run ID, authorization reference, and authorization hash
all fail closed.

## Exact provider requests and pacing

The in-process HTTPS transport constructs the Authorization header. It never uses a
shell, `curl`, redirect, query-supplied secret, or retry. Request starts are spaced by
at least one monotonic second inside the 60-second provider deadline.

| # | Request ID | Method and exact path | Response cap |
|---:|---|---|---:|
| 1 | `account-workspace-identity` | `GET /api/v1/audit-events?resource_type=cloud.api_key` | 262,144 B |
| 2 | `instance-types` | `GET /api/v1/instance-types` | 262,144 B |
| 3 | `images` | `GET /api/v1/images` | 262,144 B |
| 4 | `regions` | `GET /api/v1/regions` | 262,144 B |
| 5 | `ssh-keys` | `GET /api/v1/ssh-keys` | 262,144 B |
| 6 | `firewall-rulesets` | `GET /api/v1/firewall-rulesets` | 262,144 B |
| 7 | `global-firewall-ruleset` | `GET /api/v1/firewall-rulesets/global` | 262,144 B |
| 8 | `running-instances` | `GET /api/v1/instances` | 262,144 B |

Pagination is not authorized. A non-null audit page token is retained only as
`source_page_complete: false`; it causes no ninth request.

## Exact caps

| Resource | Aggregate cap | Per-operation cap |
|---|---:|---:|
| Provider calls | 8 GET; 0 mutation calls | one request per listed path |
| Provider raw response | 2,097,152 B | 262,144 B per response |
| Request pacing | >=1 s between starts | counted inside provider wall |
| Provider wall | 60 s | remaining absolute deadline passed to each DNS/connect/TLS/read operation |
| Archive/finalization wall | 60 s | a separate monotonic watchdog process is armed immediately before archive I/O and SIGKILLs the supervisor on expiry; storage observations also have 10 s subprocess timeouts |
| Whole supervisor wall | 180 s | a separate monotonic watchdog process is armed before repository/secret/storage/provider work and SIGKILLs the supervisor on expiry |
| Automatic retries | 0 | 0 for every provider/local operation |
| Local process calls | 14 | 2 secret-scrubbed deadline watchdogs, 3 bounded Git state reads, and 9 read-only `diskutil` calls |
| Local process output/control | 37,814,274 B | 65,536 B across Git reads; 4,194,304 B per `diskutil` call; exactly one readiness byte from each watchdog; watchdog stdout/stderr 0 B |
| Local redacted artifact | 524,288 B | one exclusive file create |
| Local copy record | 65,536 B | one exclusive file create |
| External sealed bundle | 1,048,576 B | three files: artifact, `COPY_RECORD.json`, `SEAL.json` |
| Total retained bytes | 1,638,400 B | local and external maxima combined |
| File/directory creates | 2 local files; 3 external files; <=4 external directories | no overwrite; fixed hierarchy/run identity only |
| Mac mini prewrite free floor | 8,591,048,704 B | checked before any provider request |
| Mac mini retained free floor | 8,589,934,592 B | checked after local record finalization |
| External retained-free floor | `max(161,061,273,600, ceil(current_capacity_bytes/5))` | pre-copy adds 1,048,576 B |
| Provider/API/compute charge | USD 0.00 | no paid compute |
| Model calls/tokens, browser actions, SSH, SiRA | 0 | 0 |

The exact external hierarchy may be created beneath the already approved mount only
after a fresh identity check. There is no internal-disk fallback.

## Exact local arrays and write contract

The future supervisor entry is this shell-free argv array with the three marked
values replaced by the exact final handoff/authorization values:

```json
[
  ".venv/bin/python",
  "-m",
  "giclab.harness.lambda_inventory",
  "--repository-root",
  "/Users/joseph/.codex/worktrees/84b1/gic-lab",
  "--plan",
  "/Users/joseph/.codex/worktrees/84b1/gic-lab/containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan.json",
  "--plan-sha256",
  "c7151737bd029e3ebad45d59dc2d9fcd58f401dc7d8658021f1d384129555c69",
  "--expected-commit",
  "<EXACT_FINAL_GATE_L0_COMMIT>",
  "--authorization-reference",
  "<FRESH_AUTHORIZATION_REFERENCE>",
  "--authorization-sha256",
  "<SHA256_OF_FRESH_AUTHORIZATION_TEXT>"
]
```

The storage observer may invoke only:

```json
["/usr/sbin/diskutil", "info", "-plist", "/Volumes/Macintosh HD - Data"]
["/usr/sbin/diskutil", "info", "-plist", "/System/Volumes/Data"]
["/usr/sbin/diskutil", "apfs", "list", "-plist"]
```

The repository guard may invoke only:

```json
["/usr/bin/git", "branch", "--show-current"]
["/usr/bin/git", "rev-parse", "HEAD"]
["/usr/bin/git", "status", "--porcelain=v1", "--untracked-files=normal"]
```

The supervisor also creates exactly two shell-free, zero-stdout/stderr watchdog helpers,
one for 180 seconds and one for the 60-second archive phase. Each helper receives
only an inherited control descriptor, the exact parent PID, and the numeric cap:

```json
[
  [
    "/Users/joseph/.codex/worktrees/84b1/gic-lab/.venv/bin/python",
    "-m",
    "giclab.harness.lambda_inventory",
    "_deadline-watchdog",
    "<INHERITED_DISARM_FD>",
    "<INHERITED_READY_FD>",
    "<EXACT_PARENT_PID>",
    "180"
  ],
  [
    "/Users/joseph/.codex/worktrees/84b1/gic-lab/.venv/bin/python",
    "-m",
    "giclab.harness.lambda_inventory",
    "_deadline-watchdog",
    "<INHERITED_DISARM_FD>",
    "<INHERITED_READY_FD>",
    "<EXACT_PARENT_PID>",
    "60"
  ]
]
```

Each helper must return exactly one `R` byte through its inherited readiness pipe
within two seconds; otherwise the supervisor kills it and stops before sensitive
work. Every watchdog, Git, and `diskutil` child receives exactly this newly
constructed environment: `PATH=/bin:/usr/bin`, `LANG=C`, `LC_ALL=C`,
`PYTHONNOUSERSITE=1`, `GIT_CONFIG_NOSYSTEM=1`, and
`GIT_CONFIG_GLOBAL=/dev/null`. It never inherits `LAMBDA_API_KEY`, `SIRA_API_KEY`,
`OPENAI_API_KEY`, or any other host environment entry. Each helper accepts only its
actual parent PID and one of the two approved deadlines, uses a monotonic timer, and
exits on control-pipe disarm/EOF. On expiry it sends SIGKILL only to that parent.
There is no shell, retry, captured output, or cleanup broadening. The 180-second
watchdog remains armed while the 60-second archive watchdog is created and closed.

It performs one three-call observation before provider access and fresh pre/post-copy
observations. The archive path must resolve to writable, unlocked APFS volume UUID
`8478609D-FA37-4ED5-875D-47AE912B9151`, physical-store UUID
`7904A6F1-F483-4ED7-9E34-BFECAB31C63E`, external Thunderbolt/UTDM state, and the
dynamic free-space floors. Held no-follow descriptors bind the external mount,
system mount, repository root, and archive root through the copy. Source and
destination must be different filesystems.

The local artifact is canonical/schema-valid before copy. The external staging
directory is fresh, all three files are created exclusively, fsynced, set read-only,
verified by SHA-256, and atomically renamed to the exact run ID. A fresh post-copy
volume check is required. The local source stays in place, and a separate local
verification record binds destination hashes, seal hash, volume identities, post-copy
free space, plan, run, commit authorization, and source retention. L2 may consume the
inventory only when both local files and the external sealed bundle verify.

## Secret, parser, redaction, and selection contract

The only secret name is `LAMBDA_API_KEY`. The user supplies it outside Git through the
supervisor secret channel. It exists only in memory and the HTTPS Authorization
header; it is never printed, hashed, persisted, returned, placed in argv/URL/path/log,
included in evidence, or inherited by a child process. `SIRA_API_KEY` and
`OPENAI_API_KEY` are rejected fallbacks.
Raw provider responses remain memory-only.

The parser validates the exact DTO field sets and every retained or decision-bearing
type. It rejects duplicate keys, non-UTF-8/malformed/deep JSON, `NaN`/`Infinity`,
missing/extra responses, cap excess, unknown architecture/protocol values, invalid
IPv4 CIDRs, inconsistent identities, and ambiguous account/workspace bindings. It
does not claim to type-check every discarded provider field or refetch the OpenAPI
document during L1; the committed OpenAPI hash is the design lock, while DTO drift
stops parsing.

Retained evidence contains domain-separated account/workspace hashes; type, price,
resource and region facts; exact image identity; SSH key ID/name without public-key
text; firewall ID/scope/protocol/port/source CIDR without free-text descriptions; and
running-instance identity/state without instance IP/Jupyter data. It explicitly says
instance IPs are absent while firewall source CIDRs are retained.

Selection is stable by `(price_cents_per_hour, instance_type_name, region_name,
image_id)` after requiring current capacity, x86_64, >=8 vCPU, >=16 GiB RAM, >=100 GiB
root, <=150 cents/hour, at most one GPU, exact regional `gpu-base-22-04` x86_64 image,
an effective TCP/22-only firewall, and a region other than documented-firewall-exempt
`us-south-1`. A duplicate T07 instance or no qualifying tuple seals a typed blocked
artifact and stops without escalation.

## Stop conditions and remaining blockers

Stop with no retry if any authorization, branch, commit, clean-tree, plan, run,
endpoint, method, pace, deadline, response, DTO, redaction, candidate, secret, volume,
path, device, free-floor, create, byte, fsync, hash, atomic-rename, or retained-floor
contract fails. Partial external staging is retained for manual evidence review; the
supervisor never broad-cleans or overwrites it.

Gate L1 still requires a fresh explicit user authorization and availability of
`LAMBDA_API_KEY`. The archive hierarchy is currently absent; the authorization below
explicitly permits creation of only its fixed components. Gate L2 remains additionally
blocked on successful archived L1 evidence, exact account facts, a user-approved
existing key/ruleset, a source-backed SSH server-host-key trust bootstrap, a new
account-bound plan, and fresh L2 authorization.

## Ready-to-copy Gate L1 authorization block

```text
I authorize T07 Gate L1 read-only Lambda inventory only on the exact clean
phase-1/sira-smoke-lambda commit reported in the Gate L0 handoff, using run
RUN-T07-L1-LAMBDA-INVENTORY-0001 and plan
PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V1 at
containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan.json, SHA-256
c7151737bd029e3ebad45d59dc2d9fcd58f401dc7d8658021f1d384129555c69.

The operator may read LAMBDA_API_KEY only through the documented nonlogging secret
channel and issue exactly the eight listed GETs to https://cloud.lambda.ai, once each,
in order, with starts at least one second apart, no pagination and no retry. Caps are:
60 seconds provider wall, 60 seconds archive wall, 180 seconds total wall; 2,097,152
raw response bytes; 524,288 local artifact bytes; 65,536 local verification-record
bytes; 1,048,576 external sealed-bundle bytes; and 1,638,400 aggregate retained bytes.

I also authorize the exact read-only Git/diskutil checks and creation, if absent, of
only /Volumes/Macintosh HD - Data/GIC-Lab,
/Volumes/Macintosh HD - Data/GIC-Lab/t07, and
/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts, followed by one fresh
RUN-T07-L1-LAMBDA-INVENTORY-0001 staging/final directory. The copy must bind the
documented APFS/physical-store UUIDs through held no-follow descriptors, enforce the
8,591,048,704-byte Mac mini prewrite floor, 8,589,934,592-byte retained floor, and the
dynamic external floor plus 1,048,576 bytes, verify source/destination SHA-256, fsync,
atomically finalize, retain the source, and leave no internal fallback.

This authorization permits zero Lambda/cloud mutation, instance launch/termination,
paid compute, SSH, model/provider-model call or token, browser action, SiRA execution,
and scientific-field change. It forbids reading SIRA_API_KEY or OPENAI_API_KEY. Stop
on any contract failure and do not begin Gate L2.
```

# T07 Gate L3 Lambda B2b requirements

Status: **requirements only; blocked until successful Gate L2; unauthorized and
non-executable**

Gate L2.0 ended at `blocked-human-or-source-decision`; its proposed V1 plan/run
identities were rejected and must not be reused. Gate L2.1's independent review then
terminated the automated API-launch path at `manual-console-launch-required`; its
draft V2 identities are also rejected. Gate L2.2 subsequently stopped the
human-console/Jupyter route at `blocked-human-image-selection`. Gate L2.3 has now
validated the user's private `img-0032` selection and rendered
the repaired `PLAN-T07-GATE-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-V2`, but that plan remains
unauthorized and unexecuted. Gate L3 still requires a separately authorized and
successful human-operated Gate L2M run with
externally sealed success evidence, exact provider termination, restored firewall
state, and zero owned residue. The proposed BusyBox probe is a non-executable Gate L2
design input only and cannot substitute for the three Gate L3 image/browser/
dummy-secret probes.

This document supersedes `docs/harness/T07_GATE_B2B_REQUIREMENTS.md` only for the
selected future Lambda x86_64 topology. The older local/arm64 document remains
terminal rejected provenance and is not rewritten. This document has no Gate L3 plan
ID, plan hash, account/instance binding, command array, authorization reference or
authorization block. Gate L2M's separate plan and private binding cannot become Gate
L3 authority.

## Entry conditions

Gate L3 may be materialized only after a separately authorized Gate L2 has sealed
schema-valid evidence of:

- exact sealed Gate L1 authorization/plan/commit/ledger plus selected Lambda
  type/region/image/key/ruleset/price/instance identity;
- the private approval of `img-0032` / Lambda Stack 22.04 / `22.4.5-2141` bound by
  Gate L2.3, plus the pre-mutation launch-wizard offeredness checkpoint;
- x86_64 OS/kernel and private PID/cgroup/IPC behavior;
- exact Docker client/server, containerd, runc, cgroup driver and log driver;
- one immutable BusyBox containment probe with bounded stop/KILL cleanup and zero
  residual resources;
- no host/runtime/package mutation, no persistent Lambda filesystem, no browser/model/
  SiRA action, complete evidence transfer, provider termination, and nonbillable state;
- exact actual provider wall and estimated list cost within the Gate L2 caps.

L2 success authorizes no L3 download, pull, build, dependency installation, browser,
dummy-secret probe, or SiRA action. L3 needs a new design packet and authorization.

## Immutable x86_64 workload inputs

A future L3 plan must revalidate and bind, never silently replace:

| Input | Exact identity |
|---|---|
| Playwright base index | `mcr.microsoft.com/playwright/python:v1.39.0-jammy@sha256:96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c` |
| linux/amd64 platform manifest | `sha256:8f7d4d5ef52dbe4af81db537258ae6d15c71b86c6984dd6030dac8f34c86ebcd` |
| linux/amd64 config | `sha256:801969079a1e0ae8c657adc45f7acac5abcc7fab846e60cd42c883ee78dded51` |
| Compressed base layers | 742,924,281 B |
| Python/browser | Python 3.10; Playwright 1.39.0; Chromium revision 1084 / browser 119.0.6045.9 |
| SiRA source | commit `93fb8d72de71f9a4a13419670adeb34d93cf7acd` |
| Model-routing patch | `containers/sira-smoke/sira-immutable-model-routing.patch`, SHA-256 `4d7e2a25f4313fc754db0fa17aeda51cc5cd75a5653adaf13b01ce87a71cb8ed` |
| Frozen dependency lock | upstream `uv.lock`, SHA-256 `138585129c7f369887591d30d9727f8dd466639fa78fb00adc5a04f1e9b2d76e` |
| Dependency operation | `uv sync --frozen --extra eval`; no unlock/update/fallback |
| Scientific model | `gpt-4o-2024-11-20` for every SiRA module/role/fallback; not called in L3 |

The existing `containers/sira-smoke/Containerfile` is an arm64 historical artifact
and cannot be used unchanged. A future L3 design must create a separately hashed
x86_64 build file and provenance record without rewriting the historical file. The
base image must be pulled by the exact index and verified to the exact amd64 manifest
before build. BuildKit may not refresh `FROM`, source, browser, or dependencies beyond
the approved locks.

The build context must copy a clean pinned SiRA checkout, exact lock, repository-owned
patch, Gate A routing adaptation, fixtures, and an explicit allowlist. It must reject
Git dirt, extra files, symlinks, missing hashes, generated credentials, mutable tags,
and unapproved network endpoints. The routing patch is applied as a distinct hashed
artifact; the upstream checkout remains clean.

## Required image provenance

The future record must include:

- base index, amd64 manifest, config and every layer digest/byte count;
- x86_64 build-file path/hash and canonical build argument array;
- clean SiRA source commit and tree hash;
- routing-patch path/hash and apply-check/apply evidence;
- `uv.lock` hash and the exact selected wheel/sdist URLs, bytes and hashes;
- installed package manifest and manifest hash;
- Playwright package version, Chromium revision/version, executable path/hash and
  browser asset manifest;
- final image ID, every repo digest, architecture/OS, labels and inspect document;
- Gate L2 host/runtime evidence hash, Gate L3 plan/authorization hashes, repository
  commit and attempt identity;
- bounded network/download/build-cache/root-disk/output/wall/call deltas.

A final image tag is only a local convenience and never authority; workload
containers use the observed immutable image ID.

## Three no-provider probes

Gate L3 executes exactly these infrastructure probes, in order, with zero automatic
retry:

1. adversarial descendant-containment fixture;
2. public dummy-secret canary fixture;
3. local static-page Chromium fixture.

It makes zero OpenAI/model/provider-model calls, uses zero model tokens, executes zero
SiRA conditions, and contacts no live website. Mock tests validate the control plane;
the three containers empirically validate the qualified host/runtime and built image.

| Probe | CPU | Memory/swap | PIDs | Workload wall | Retained payload/log/evidence | Private shm | each tmpfs | TERM |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Adversarial containment | 1.000 | 536,870,912 B | 64 | 30 s | 16,777,216 B | 67,108,864 B | 67,108,864 B | 1 s |
| Dummy-secret canary | 1.000 | 536,870,912 B | 64 | 30 s | 16,777,216 B | 67,108,864 B | 67,108,864 B | 1 s |
| Local-page Chromium | 2.000 | 2,147,483,648 B | 256 | 60 s | 33,554,432 B | 1,073,741,824 B | 134,217,728 B | 2 s |

Aggregate fixed probe maxima remain 3 containers, 120 workload seconds, 67,108,864
retained bytes, at most 96 container-lifecycle CLI calls, 1 local browser navigation,
1 local screenshot, USD 0 model/API cost, 0 model tokens/calls, and 0 SiRA executions.
A future plan must add exact x86_64 image/dependency/build downloads, root/build-cache
disk, provider wall/cost, SSH transfer, seal-copy and host-command caps from current
metadata; no null/unbounded term is executable.

## Container and containment contract

Each probe receives a fresh attempt UUID/container name and immutable container ID.
The ID—not host descendant enumeration—is the authoritative lifecycle handle. Every
container requires:

- private PID and cgroup namespaces, private IPC, network `none`, no host namespace;
- no privileged mode, runtime socket, host device, SSH-agent forwarding, broad host
  mount, capability add, or rootfs write;
- `cap-drop=ALL`, no-new-privileges, init, restart `no`, read-only root, finite local
  log rotation, bounded `/tmp`, `/run` or `/run/secrets`, and private shm;
- finite CPU, memory+swap, PID, wall, output, log, evidence and disk bounds;
- immutable source/config copied or baked through a hash-checked bounded mechanism;
- create/inspect/start/pre-stop process evidence/stop/KILL/terminal inspect/logs/
  pre-removal evidence/remove/residual scan/seal by exact ID;
- a typed provider-instance termination `finally` path for any VM/runtime failure;
- no host `setsid`, killpg, `pkill -P`, polling or process-tree enumeration fallback as
  the containment proof.

The adversarial fixture must fork children/grandchildren, create a new session/process
group, double-fork or reparent where possible, ignore TERM, and spawn until the PID
limit blocks it. Passing requires bounded stop, required KILL escalation, full
container-boundary termination, and zero owned residual process/container/network/
volume/helper state.

## Dummy-secret contract

Gate L3 uses only the public dummy canary. It is created outside Git under the fresh
attempt root, made available only as a file `/run/secrets/sira_api_key`, and never
placed in an image, build argument, argv, environment list in container config, label,
path name, log, screenshot, manifest, inspect record, or evidence. The in-container
entrypoint reads the file and exports `SIRA_API_KEY` only to its child process.
`OPENAI_API_KEY` is rejected as an undeclared fallback.

The supervisor scans commands, build inputs, labels, inspect documents, logs,
screenshots, manifests, retained output and sealed evidence for the canary before
owned-file cleanup. The real `SIRA_API_KEY` and `OPENAI_API_KEY` remain unread and out
of scope. A future separately authorized Lambda host lifecycle would require
`LAMBDA_API_KEY` only in its nonlogging provider-control supervisor through terminal
confirmation; it is never injected into a probe container or materialized as
dummy-secret evidence.

## Browser-only contract

The Chromium fixture may open exactly one bundled `file://` static page or
`about:blank`, make one local navigation, capture one local screenshot, close the page,
context, browser and Playwright driver, and exercise container shutdown. The container
has network `none`; no DNS, localhost server, external URL, extension, authentication,
model client, SiRA command, or experimental BrowserGym task is permitted.

## Evidence, storage, and provider cleanup

Active bounded evidence remains on the ephemeral Lambda root and is copied to a fresh
bounded Mac mini attempt root with source/destination SHA-256 verification. The remote
source remains until transfer verification; provider termination cannot be delayed by
a failed copy. After termination, the Mac mini source is writer-closed, regular-file
validated, fsynced, hashed and sealed, then copied one-way to the approved D-018
MacBook archive under a fresh volume/identity/free-floor guard. Destination hashes and
durability evidence are mandatory; local source remains until independent archive
verification. No live bidirectional synchronization or Lambda persistent filesystem
is allowed.

Cleanup may target only exact owned IDs and fresh paths. Runtime-wide prune, unrelated
container/image/network/volume deletion, broad kill, account key/firewall/filesystem/
tag mutation, historical evidence deletion, or internal-disk fallback is prohibited.
Every exit after Lambda launch ends in provider-API termination and terminal/
nonbillable confirmation.

## Scientific and next-gate boundary

Gate L3 is infrastructure qualification only and preserves:

```text
EXP-0001
PLAN-EXP0001-SMOKE
SIRA-REACTIVE first
SIRA-SIMULATIVE second
PAIR-EXP0001-SMOKE-0000
gpt-4o-2024-11-20
directional reproduction
interpretation_allowed: false
pilot unauthorized
training false
```

Only a fresh Gate L4 authorization may launch a fresh qualified Lambda host, use the
real secret channel, call OpenAI, and execute the one locked pair. L3 creates no Gate
L4 authority.

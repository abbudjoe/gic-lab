# T07 Gate B2b requirements

Status: **requirements only; blocked by rejected runtime candidate; unauthorized**

This document has no plan ID, plan SHA-256, executable argument array, runtime path,
attempt UUID, authorization reference, or authorization block. It cannot be executed.
The older Docker-specific requirements stub remains historical provenance.

## Entry conditions

Gate B2b may be designed only after the user selects and separately approves one of
the terminal Gate B1.7 alternatives and a qualification equivalent to B2a produces
sealed evidence for all of the following:

- exact installed runtime/VM/client/server versions, source identities, executable
  hashes, OS, architecture, cgroup implementation, and immutable VM image;
- a storage topology that can hold runtime state and required credentials without
  violating ownership/confidentiality policy;
- a numeric Mac mini/host operational floor and exact per-stage and aggregate disk,
  download, output, call, and wall caps;
- fresh stable storage identity plus a held-descriptor guard before and across every
  sensitive operation, with no internal fallback;
- closed and exact network endpoint behavior for installation and first start;
- exact profile/VM/runtime state before stop, after stop, after reconnect/restart, and
  after final stop;
- typed zero-retry rollback and supervisor-owned writer-probe/seal/copy evidence;
- no workload image pull/build, browser, secret, provider/API, or SiRA condition in the
  qualifying gate.

The rejected Colima candidate does not satisfy those conditions. In particular,
`containers/sira-smoke/colima/` contains no executable plan.

## Immutable B2b inputs

A future B2b design must rebind, not silently replace:

- native `linux/arm64` Playwright base index
  `mcr.microsoft.com/playwright/python:v1.39.0-jammy@sha256:96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c`;
- arm64 platform manifest
  `sha256:f8fca31a4730afa691e73ed99b4a6ebf28b2a9bd65a7038bb6da4bd223bb237b`;
- SiRA commit `93fb8d72de71f9a4a13419670adeb34d93cf7acd`;
- Python 3.10, `uv sync --frozen --extra eval`, Playwright 1.39.0, Chromium
  revision 1084 / browser 119.0.6045.9;
- repository-owned Containerfile, immutable-routing patch, Gate A adaptation,
  fixtures, lock hash, and build-context allowlist;
- final local image by observed immutable `sha256:` image ID, never a tag;
- installed-package manifest, browser executable hash, and full image provenance.

No platform fallback to amd64, Rosetta, QEMU, a floating image tag, mutable source, or
unfrozen dependency resolution is allowed.

## Workload-container policy

Every probe container must use a fresh attempt UUID and immutable container ID as the
authoritative descendant-containment handle. It must have:

- private PID and cgroup namespaces and private IPC;
- network exactly `none`;
- no privileged mode, host PID/network/IPC, runtime-socket mount, capability addition,
  SSH-agent forwarding, or host-home mount;
- `cap-drop=ALL`, no-new-privileges, init, restart `no`, and read-only root;
- exactly one harness-owned attempt root writable plus bounded `/tmp`, `/run/secrets`,
  and private shm;
- immutable source/configuration inputs only, copied or baked by a bounded hash-checked
  mechanism rather than a mutable scientific-evidence bind mount;
- finite CPU, memory and memory+swap, PID, workload/lifecycle wall, output, log,
  evidence, tmpfs, shm, and disk limits;
- create/inspect/start/process-evidence/stop/kill/terminal-inspect/pre-removal-evidence/
  remove/residual-scan/seal lifecycle operations by immutable container ID;
- a separately typed VM-level last-resort stop for a failed container runtime;
- no authoritative host process-group or descendant-enumeration fallback.

Mock tests do not prove those kernel properties. B2b must prove them empirically on
the selected qualified runtime.

## Required fixtures and fixed workload caps

These existing scientific-infrastructure probe caps remain the maximum candidate
values. A future executable plan must also add numeric lifecycle, image, runtime-disk,
and aggregate host-storage caps; those are currently null because the runtime was
rejected.

| Probe | CPU | Memory/swap | PIDs | Workload wall | Output: payload/log/evidence | Private shm | each tmpfs | TERM |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Adversarial containment | 1.000 | 536,870,912 B | 64 | 30 s | 16,777,216 B: 8,388,608 / 2,097,152 / 6,291,456 | 67,108,864 B | 67,108,864 B | 1 s |
| Dummy-secret preflight | 1.000 | 536,870,912 B | 64 | 30 s | 16,777,216 B: 8,388,608 / 2,097,152 / 6,291,456 | 67,108,864 B | 67,108,864 B | 1 s |
| Browser-only local preflight | 2.000 | 2,147,483,648 B | 256 | 60 s | 33,554,432 B: 16,777,216 / 4,194,304 / 12,582,912 | 1,073,741,824 B | 134,217,728 B | 2 s |

Aggregate fixed probe maxima are USD 0 API cost, 0 model tokens, 0 model/API calls, 3
container attempts, 120 workload seconds, 1 local browser navigation, 1 screenshot,
67,108,864 retained output bytes, and at most 96 container-lifecycle CLI calls through
fixed state machines. Per probe: 32 lifecycle calls; API cost/tokens/calls are all
zero; browser actions are 0, 0, and 1 respectively. Automatic retry is zero.

The adversarial fixture must fork children and grandchildren, create another session
and process group, double-fork/reparent when possible, ignore TERM, and spawn until the
PID limit blocks it. Success requires stop then kill escalation to terminate the
entire container boundary and proof that no descendant/residual resource survives.

The browser fixture may navigate exactly once to the bundled local static page or
`about:blank`, capture exactly one local screenshot, close Chromium/Playwright, and
exercise shutdown. It may not contain a SiRA condition or provider/model client.

## Dummy-secret contract

Only the public dummy canary is permitted. A future fixture must:

- create the canary outside the repository under a fresh owned local root;
- mount it as a file at `/run/secrets/sira_api_key` only for that container;
- never place it in an image, argv, label, path name, inspect configuration environment
  list, retained command, or log;
- let the in-container entrypoint read it and export `SIRA_API_KEY` only to the child;
- reject `OPENAI_API_KEY` as an undeclared fallback;
- scan retained commands, labels, inspect output, logs, screenshots, manifests, and
  evidence for the canary before cleanup;
- remove only the owned public dummy file after successful scan and evidence capture.

The real `SIRA_API_KEY` remains out of scope.

## Cleanup and sealing

For each fixture, B2b must capture container ID, pre-stop process evidence, bounded
stop and kill escalation, terminal/final inspect, bounded logs, and pre-removal
evidence before removal. It must then prove no matching running or stopped container,
owned network, owned volume, owned VM helper, or labeled auxiliary resource remains.

Cleanup may target only immutable owned IDs and fresh exact paths. Runtime-wide prune,
host descendant enumeration, broad process killing, unrelated-profile deletion, prior
evidence deletion, and internal-disk fallback are prohibited. Failure retains local
evidence and partial sealed-copy state.

After all writers close, the supervisor-owned in-process driver must run the bounded
writer probe, fsync and hash every regular file, reject symlinks/nonregular files,
seal the source immutable, copy one-way to the approved durable volume, verify every
destination SHA-256, fsync and atomically finalize the destination, record both volume
identities and hashes, and retain the local source until independent verification.

## Scientific boundary

Gate B2b is infrastructure qualification only. It must preserve:

```text
EXP-0001
PLAN-EXP0001-SMOKE
SIRA-REACTIVE first
SIRA-SIMULATIVE second
gpt-4o-2024-11-20
interpretation_allowed: false
pilot unauthorized
cloud mutation false
training false
```

It may not execute either SiRA condition, call a provider/model API, begin Gate C or
the pilot, change a scientific field, or authorize cloud/training/paid compute.

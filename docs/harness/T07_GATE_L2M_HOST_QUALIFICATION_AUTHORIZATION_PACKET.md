# T07 Gate L2M host-qualification authorization disposition

Status: **blocked-human-image-selection; unauthorized; no executable plan**

Date: 2026-08-10

This path is intentionally a terminal disposition rather than an authorization
packet. The existing private decision binds GPU Base 22.04, which lacks a documented
JupyterLab guarantee. Four Lambda Stack 22.04 regional candidates exist, but a new
human selection is required. Static source evidence does not prove type-specific
launch-wizard offeredness; a future run must fail closed before Launch unless the
approved alias/version is visibly offered after selecting `gpu_1x_a10` and
`us-east-1`. No plan or ready-to-copy authorization may be issued from this record.

## Proposed qualification input, not authority

- Recommended image: `img-0032`, `lambda-stack-22-04`, `22.4.5-2141`, x86-64,
  `us-east-1`, Python 3.10, documented Docker and JupyterLab.
- Instance type: `gpu_1x_a10`; sealed observed rate USD 1.29/hour.
- SSH key: `fractal-lambda-codex`, launch-wizard input only; zero SSH use.
- Persistent filesystem: none.
- Access: user-operated Lambda Cloud IDE/Jupyter only.
- BusyBox:
  `busybox@sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0`,
  `linux/amd64`, config `sha256:db287cb6…30e4`, one 2,211,507-byte compressed
  layer `sha256:436a1b1f…2ab`.

## Bundle identities

Manifest: `containers/sira-smoke/lambda/manual-console/manifest.json`, 1,510 bytes,
SHA-256 `dc9824649f97fab6cfd105b5fc0d0c6c1c5ff513fa25f70e0d517afa623cc261`.

| File | Bytes | SHA-256 |
|---|---:|---|
| `adversarial-containment.sh` | 1,273 | `67c80f74069c4260a5131fa6311d7394e645fe14fdd078de59583447a25b6355` |
| `docker_inspector.py` | 23,123 | `6995c486a4945159a33d2aac5837569ab66dc459033b185eb57968f6fc5ae230` |
| `evidence_packager.py` | 14,825 | `7db3a4cfd6ba5e8b20fc95ad2f2301555a23b394b75044ef8ac592215b08b28a` |
| `host_facts.py` | 6,277 | `a0010817187a419fc0f1497861b4920724a1b43d0edf613f082eb68eb6042cc1` |
| `public-source-observations-l2-2.json` | 6,815 | `56a1ba759d4fc5ac6eba2ee85c5bff2a08d0d71f538793f3de5732bb80d0b1a5` |
| `qualification_driver.py` | 62,821 | `ab9a3f8981d2e60ea5b57bb7cf63512f64cdb89f26d8183788aedc2dbe4b5050` |

The bundle is designed for one future manual upload and one exact argument-array
invocation. It performs no apt/dependency install, runtime update/reconfiguration,
SSH, browser, model, SiRA, or science. Static/fake tests do not prove Lambda, Jupyter,
Docker, kernel containment, evidence download, provider termination, or billing.
Before any Docker call, it requires the manifest-bound public BusyBox observation to
match every pinned OCI identity and be no more than 86,400 seconds old. It records
repository-record validation separately from the earlier public-registry read and
makes no standalone registry-metadata request during qualification.

## Proposed future caps, not authorized

- 1 human launch click; 1 instance; 0 filesystems; 0 automated Lambda/cloud-account
  mutations (provider mutations remain explicit user-console actions); finite
  automated in-host Docker lifecycle calls are separately capped below;
- 44 read-only Lambda GETs, 1,048,576 bytes each and 16,777,216 aggregate;
- phase GET caps: preflight 5, strict-global verify 1, ruleset bind 1, instance
  bind/active 10, Cloud IDE 0, qualification/download 0, termination verify 10,
  ruleset absence 2, global restoration 1, and incident reserve 14;
- 1-second request spacing, no automatic retry, redirect, or pagination;
- 6,300-second observer total wall: 1,200 prelaunch + 3,600 provider + 1,200
  post-provider cleanup + 300 archive; 512 events; 2,097,152-byte journal;
- 32 Docker calls; 1 container; 30-second fixture wall; 8,388,608 Docker-output bytes,
  of which 1,048,576 are reserved exclusively for cleanup and unavailable to ordinary
  work;
- ten of the 32 Docker calls reserved from ordinary work for emergency
  kill/remove/residue proof; an outcome-unknown create may additionally use its
  early-path unused headroom for five identity polls, one recovered-ID inspect, and
  three stable-absence polls while remaining within 32; 270 seconds ordinary Docker
  work and 300 seconds including emergency cleanup;
- 16,777,216-byte source and ZIP cap per remote evidence set; 34,603,008 remote
  retained source bytes, 33,554,432 retained archive bytes, and 68,157,440 aggregate;
  33,554,432 unpacked bytes, 83,886,080 Mac-active bytes, and 41,943,040-byte external
  sealed archive;
- 1,800-second normal termination-click deadline, 3,600-second hard provider wall,
  USD 2.00 cost ceiling, and USD 1.29 modeled one-hour list cost before tax;
- zero SSH, browser automation, model calls/tokens, SiRA, or scientific execution.

## Blockers before any authorization

1. The user must make and privately materialize the new image and manual-action
   decisions defined in `T07_GATE_L2M_MANUAL_CONSOLE_DECISION_PACKET.md`.
2. A later offline materialization must validate/seal that file, mint a fresh marker,
   create fresh plan/run/checkpoint/archive identities, revalidate current
   price/capacity/images/zero-running state and global firewall, bind the clean commit
   and every schema/bundle hash, publicly re-read the exact BusyBox manifest-by-digest
   without downloading a layer, regenerate the source-record/driver/host-schema/
   manifest identities so the observation will be at most 86,400 seconds old at pull,
   and undergo independent review.
3. A fresh current-turn authorization must explicitly permit the exact user console
   mutations, read-only observer requests, one BusyBox pull, one containment container,
   paid-compute ceiling, evidence copy, termination, ruleset deletion, and global
   restoration.
4. Cloud IDE under the strict firewall remains an empirical stop condition because no
   first-party source proves firewall independence. Failure permits cleanup only, not
   an additional port.

There is no plan ID/path/bytes/SHA, authorization reference, execution commit, or
ready-to-copy authorization block. Gate L3 and Gate L4 remain blocked.

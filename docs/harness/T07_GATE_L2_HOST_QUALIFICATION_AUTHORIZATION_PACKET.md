# T07 Gate L2 host qualification authorization disposition

Status: **blocked; no authorization packet; no executable plan**

Date: 2026-08-10

Gate L2.0 ended in `blocked-human-or-source-decision`. This file exists at the
required packet path only to make the absence of mutation authority explicit. It is
not a ready-to-copy authorization packet.

## Bound offline facts

- Branch: `phase-1/sira-smoke-lambda`.
- Required starting commit: `314270ecd27115d801ea6348ac7653d30d56a884`.
- Private decision path: `~/.config/gic-lab/t07/l2-human-decisions.json`.
- Private decision SHA-256:
  `0b109b0150eec8739e30e86e5f1318b60c818cc3974354c67dc35a4e2dffd4ea`.
- Public decision alias: `l2-decision-6cb543526ab1`.
- Selected public tuple: `gpu_1x_a10`, `us-east-1`, `x86_64`, 30 vCPU,
  200 GiB RAM, 1,400 GiB root, one GPU, USD 1.29/hour.
- Image: alias `img-0111`, family `gpu-base-22-04`, version `22.4.5-2141`.
- SSH key: `fractal-lambda-codex`, unique sealed public-key match; future access
  preference was a preloaded macOS SSH agent without private-key reads.
- Persistent filesystem: none.
- Firewall preference: temporary strict global TCP/22 private `/32` plus one fresh
  strict same-region ruleset.
- Host-key preference: independent ED25519 evidence through authenticated Lambda
  Jupyter before SSH.
- Pinned probe image:
  `busybox@sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0`.

Raw IDs, the source network, nonce, fingerprints, local paths, and firewall values
remain only in ignored, sealed private evidence.

## Why authorization is prohibited

The pinned first-party Lambda contract does not establish a strongly consistent,
idempotent, or otherwise bounded method to identify an accepted launch after the
client observes an unknown network outcome. Ownership-friendly instance name and tag
fields are optional. A zero-result list response can therefore not prove that no
delayed billable instance exists, and the proposed exact-ID-only cleanup cannot
guarantee termination.

Independent review also found no authoritative end-to-end supervisor enforcing
authorization/commit/plan/run freshness, operation order/cardinality, response
semantics, aggregate limits, no replay, bounded SSH execution, private output
projection, complete evidence eligibility, and descriptor-held archive finalization.
These are control-plane defects, not evidence about Lambda service health.

## Non-authoritative draft controls

The Gate L2 source modules, schemas, and tests are retained as non-executable draft
controls. They may support a future implementation review but do not grant or render
authority. The invalid Docker `--pid private` draft flag was removed; private PID mode
would still require runtime inspect evidence in a future authorized design.

The human values USD 2.00 provider ceiling, 3,600-second provider wall, and
600-second checkpoint remain validated decision inputs only. No aggregate provider,
SSH, container, output, archive, storage, or tool-call cap is authorized because no
executable supervisor/plan exists.

## Rejected identities

The proposed identities below were never executed, are not present as an executable
plan, and must not be authorized or reused:

- `PLAN-T07-GATE-L2-LAMBDA-HOST-QUALIFICATION-V1`;
- `RUN-T07-L2-LAMBDA-HOST-QUALIFICATION-0001`;
- `AUTH-T07-GATE-L2-LAMBDA-HOST-QUALIFICATION-V1-PENDING`.

There is no plan path, plan byte count, plan SHA-256, clean authorization commit, or
ready-to-copy authorization block.

## Required future resolution

Before any Lambda mutation can be proposed, a future task must obtain a source-backed
launch-ambiguity and cleanup contract and implement one reviewed supervisor that
closes every blocker above. That work must create fresh plan/run identities and must
receive a fresh current-turn user authorization. Gate L3, Gate L4, paid compute,
cloud mutation, SSH, Docker, browsers, model calls, SiRA, and scientific execution
remain blocked.

# T07 Gate L2 host qualification terminal disposition

Status: **manual-console-launch-required; no authorization packet; no executable
plan**

Date: 2026-08-10

Gate L2.1 is the final automated local-runtime/API-launch selection gate. Independent
review found that the source-bound ownership design and fake-tested control primitives
do not compose an authoritative live supervisor and independently surviving cleanup
watchdog. The automated API-launch path is therefore terminated. This file occupies
the required authorization-packet path solely to make the absence of authority
explicit; it is not a ready-to-copy authorization packet.

## Bound offline facts

- Branch: `phase-1/sira-smoke-lambda`.
- Clean starting commit: `1a72670d2c5ee35566b66bcccbbf15e0942e5b1f`.
- Private Gate L2.0 decision: revalidated without printing its contents as a
  current-user-owned, mode-`0600`, no-follow regular file; 1,047 bytes; SHA-256
  `0b109b0150eec8739e30e86e5f1318b60c818cc3974354c67dc35a4e2dffd4ea`.
- Public decision alias: `l2-decision-6cb543526ab1`.
- Last sealed inventory: zero running instances.
- Selected public tuple: `gpu_1x_a10`, `us-east-1`, `x86_64`, 30 vCPU,
  200 GiB RAM, 1,400 GiB root, one GPU, observed USD 1.29/hour.
- Image: alias `img-0111`, family `gpu-base-22-04`, version `22.4.5-2141`.
- SSH key: `fractal-lambda-codex`, unique sealed public-key match.
- Persistent filesystem: none.
- Firewall design input: temporary strict global TCP/22 private `/32` plus one fresh
  strict same-region ruleset.
- Host-key design input: independent ED25519 evidence through authenticated Lambda
  Jupyter before SSH.
- Pinned containment input:
  `busybox@sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0`.

Raw IDs, source-network values, nonces, fingerprints, local paths, and firewall
values remain only in ignored/sealed private evidence.

## Pinned provider contract

The public, unauthenticated Lambda OpenAPI source is
`https://docs-api.lambda.ai/api/cloud/spec.json`, API version `1.10.0`, OpenAPI
version `3.1.0`, retrieved `2026-08-10T21:14:56Z`, 240,288 bytes, SHA-256
`320f4877924984f060b179e86595ed58918a1d0696b60b99cae548ec164934f4`.
It documents optional name/hostname/tags, list/detail observations, launch returning
instance IDs, and exact-ID termination. It does not document a launch idempotency key
or bounded visibility/consistency guarantee.

## Why no automated authorization exists

The marker and exact-match helpers improve ownership evidence, but provider fields are
optional/nonunique and an unknown post-send result still needs a complete recovery
authority. Independent review identified the following architectural blockers:

- provider mutation calls are not phase- and exact-body-authoritative; firewall
  mutation/restoration helpers can assert results rather than perform and verify them;
- post-mutation exceptions do not all enter one enforced cleanup runner;
- the primary and watchdog do not share one integrated fsync budget, mutation lease,
  heartbeat, provider boundary, or evidence closure;
- the watchdog has no concrete independently supervised entrypoint implementing
  bounded discovery, detail revalidation, termination polling, firewall recovery, and
  incident sealing;
- numeric discovery, spacing, wall, cost, SSH, Docker, transfer, and cleanup subcaps
  are not all enforced before effects;
- duplicate-instance detail revalidation and exact-ID cleanup are incomplete;
- terminal status, firewall restoration, and archive success can be asserted from
  caller-supplied state rather than derived from effect evidence;
- the process boundary does not bind exact command arrays or the full checkpoint-to-
  transfer sequence; and
- journals and V2 evidence schemas are not integrated into a nonforgeable complete
  live transaction.

These are control-plane defects, not evidence that Lambda, its API, the account, the
credential, or the selected resources are faulty. The fake-only tests prove isolated
validation behavior, not kernel containment, provider cleanup, billing termination,
or watchdog survival. The terminal decision is enforced in code: the retained concrete
HTTPS sender, subprocess runner, and watchdog spawner fail before connection, process,
pipe, or fork effects. Only fake boundaries can exercise the draft state helpers.

## Retained offline design values

The offline design derived the following numeric values; because no executable plan
exists, none is authorized:

| Category | Design value |
|---|---:|
| Launch response / normal discovery | 30 s / 300 s |
| Qualification / Jupyter checkpoint | 3,600 s / 600 s |
| Post-failure cleanup / manual response | 1,800 s / 900 s |
| Automated incident ceiling | 5,400 s |
| Normal cost ceiling / projected normal | USD 2.00 / USD 1.29 |
| Projected 5,400-second list cost | USD 1.94 |
| Provider calls / launch / termination | 420 / 1 / 4 |
| Provider response per call / aggregate | 1,048,576 B / 67,108,864 B |
| Primary and watchdog journal events | 4,096 each |
| Primary and watchdog journal bytes | 16,777,216 B each |
| Local process calls / aggregate output | 128 / 33,554,432 B |
| SSH sessions / remote commands / transfers | 33 / 33 / 33 |
| Docker calls / containers / container wall | 24 / 1 / 30 s |
| Remote evidence / transfer | 62,914,560 B / 62,914,560 B |
| Mac evidence / external archive | 67,108,864 B / 67,108,864 B |
| Mac incremental bytes | 135,266,304 B |
| Mac prewrite / retained floor | 8,725,200,896 B / 8,589,934,592 B |
| External retained / precopy floor | 200,048,192,717 B / 200,115,301,581 B |
| Filesystems / model calls / browser / SiRA / science | 0 / 0 / 0 / 0 / 0 |

The 900-second manual-response window is not proven to fit sequentially inside the
5,400-second automated ceiling; treating all three phases sequentially would be 6,300
seconds and approximately USD 2.26 at USD 1.29/hour. This unresolved arithmetic is an
additional reason the values are design evidence rather than an executable budget.

## Exact residual-risk language

> The Lambda API does not document launch idempotency. A unique name/hostname/tag
> marker plus prelaunch zero-match check and exact-ID discovery provides strong
> ownership evidence but cannot guarantee cleanup during a prolonged Lambda API and
> console outage, Mac power/network loss, or simultaneous supervisor/watchdog failure.
> In those cases a billable instance may remain until control-plane access is restored.

## Rejected and non-reusable identities

The following identities were never executed and must not be authorized or reused:

- `PLAN-T07-GATE-L2-LAMBDA-HOST-QUALIFICATION-V1`;
- `RUN-T07-L2-LAMBDA-HOST-QUALIFICATION-0001`;
- `AUTH-T07-GATE-L2-LAMBDA-HOST-QUALIFICATION-V1-PENDING`;
- draft `PLAN-T07-GATE-L2-LAMBDA-HOST-QUALIFICATION-V2`;
- draft `RUN-T07-L2-LAMBDA-HOST-QUALIFICATION-0002`; and
- draft `AUTH-T07-GATE-L2-LAMBDA-HOST-QUALIFICATION-V2-PENDING`.

There is no executable plan path, byte count, SHA-256, clean authorization commit, or
ready-to-copy authorization block.

## Terminal decision and next boundary

```text
manual-console-launch-required
```

This decision does not authorize a console launch. If the user later wants to proceed,
the next proposal must be a newly reviewed human-operated console launch/observation/
cleanup contract with fresh identities and explicit current-turn authority. It may not
reuse the automated V1/V2 identities or infer permission from either private decision
file. Gate L3, Gate L4, paid compute, cloud mutation, SSH, Docker, browsers, model
calls, SiRA, and scientific execution remain blocked.

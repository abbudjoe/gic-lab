# T07 Gate L2.0 human decisions and qualification disposition

Status: **blocked-human-or-source-decision; non-executable; unauthorized**

Date: 2026-08-10

Gate L2.0 validated and privately sealed the user's corrected host, SSH, firewall,
and host-key choices. Independent review then found a material first-party source gap
and incomplete execution-control primitives. Under the governing binary decision
rule, no executable Gate L2 plan is committed and no authorization block is issued.

This document grants no authority. Cloud mutation, paid compute, SSH, container use,
Gate L3, Gate L4, OpenAI, browsers, SiRA, the smoke pair, interpretation, and the
pilot remain blocked.

## Starting and evidence identities

- Branch: `phase-1/sira-smoke-lambda`.
- Required starting commit: `314270ecd27115d801ea6348ac7653d30d56a884`.
- Last reviewed draft-control commit before terminal adjudication:
  `c8da904bb9287f03955354bf0961779aa3e302a8`.
- Gate L1 inventory SHA-256:
  `022835438165e7e6e70dc992d6904f4e8b9448dc933d1d4c3e39ebdcc8914933`.
- Gate L1 ledger SHA-256:
  `1f94068bdb1d1d2af0075d50c1a0c06eb1c077d4128f90bdc16fd571fa6af707`.
- Gate L1 external seal SHA-256:
  `3347b8d03d0f937111de92ef79286c7fbcb02027f652f35ba42ac337cf8f7bd5`.
- Gate L1A request-ledger SHA-256:
  `41dd54aa76e8cad871f8d4064b44fb8b013a83dea96eb4494a9575df21e30e13`.
- Gate L1A private-evidence SHA-256:
  `835b5692d67fa1286a84f2b6fc0a41318693a7e28171852d01f0d6db0a7293bb`.
- Gate L1A sanitized report SHA-256:
  `28e66e39bb569327cc3d53abcc4efc07aad59e5aeb51ff0e0959f00c22c2e855`.
- Gate L1A external seal SHA-256:
  `6da847cadd75edaacb0d6c8ba69fcac375919dda85a3b4db2dad44cc6a1662f0`.

The private decision at `~/.config/gic-lab/t07/l2-human-decisions.json` was opened as
a current-user-owned, mode-`0600`, no-follow regular file. Its 1,047 bytes have
SHA-256 `0b109b0150eec8739e30e86e5f1318b60c818cc3974354c67dc35a4e2dffd4ea`.
No private field is reproduced here.

Its public binding alias is `l2-decision-6cb543526ab1`. The ignored V2 private
parameters have SHA-256
`89028846f059c305d10a741c14681c537556666ac04f290dff9be8985bfe913b`;
their seal has SHA-256
`4a6c6c3cfbf3a142b645fa361018bf6f6e6a8da99ec5ce01160d789b61b28dea`.
The local bundle seal is
`7382a8b4b4262060b2cc01f686d18444c56af918e8bb552e9bee6e470b45e555`.
Its external archive ID is
`RUN-T07-L2-LAMBDA-HOST-QUALIFICATION-0001-PRIVATE-PARAMETERS-V2`, with
archive-seal SHA-256
`bb3aeca6cbcf750680a19f0f2da01e56bc099372ea7b873890fda064b430791c`
and copy-record SHA-256
`20240e23b7ad291ad728191a4b3d6133e693515999cfaf72d9eaa30608ad91d5`.
Source and destination bytes matched; the destination was atomically finalized; the
local source remains. Raw IDs, source network, paths, fingerprints, nonce, and raw
firewall values remain private.

The earlier private bundle remains byte-preserved historical evidence. The proposed
Gate L2 V1 plan/run identities are rejected and must not be reused for execution.

## Validated public selections

| Field | Bound value |
|---|---|
| Provider | Lambda On-Demand Cloud API at `https://cloud.lambda.ai` |
| Instance type | `gpu_1x_a10` |
| Region / architecture | `us-east-1` / `x86_64` |
| vCPU / memory / root | 30 / 200 GiB / 1,400 GiB |
| GPU count | 1 |
| Observed price | USD 1.29/hour |
| Image | alias `img-0111`, family `gpu-base-22-04`, version `22.4.5-2141` |
| SSH key | `fractal-lambda-codex`, unique sealed local match |
| Access method | preloaded macOS SSH agent; private-key bytes remain unread |
| Persistent filesystem | none |
| Firewall choice | temporary strict global TCP/22 private `/32` plus fresh strict same-region ruleset |
| Host-key choice | independent ED25519 fingerprint through authenticated Lambda Jupyter |

The private bindings resolve the aliases to exact raw provider and local identities,
but those values are neither exposed here nor usable as authorization.

## Public source lock

The first-party machine-readable contract inspected without account access is:

- URL: `https://docs-api.lambda.ai/api/cloud/spec.json`;
- declared API version: `1.10.0`;
- retrieval: `2026-08-10T18:55:19.805786Z`;
- bytes: 240,288;
- SHA-256:
  `320f4877924984f060b179e86595ed58918a1d0696b60b99cae548ec164934f4`;
- prior same-version SHA-256:
  `365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded`.

The exact source and OCI metadata observations are recorded in
`containers/sira-smoke/lambda/public-source-observations-l2-0.json`.

## Pinned containment input

The rejected draft used only this public, immutable `linux/amd64` image identity:

`busybox@sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0`

- config:
  `sha256:db287cb6be81219cd18c1d82b70908f5d33eb028568b456f78eedff2ff2930e4`;
- layer:
  `sha256:436a1b1fd078ee8e117111472724c2827077657189af7a781829d0825d48d2ab`;
- compressed layer bytes: 2,211,507;
- fixture SHA-256:
  `09838913b14d23da939225cb89411619e91cb9ee023a2721b5b7c3890ac90aea`.

Nothing was pulled or run. The invalid draft Docker `--pid private` argument was
removed; Docker's default PID namespace would have to be verified by inspect in any
future, newly reviewed implementation.

## Material source blocker

The official instance response schema makes ownership-friendly name and tag fields
optional. The pinned public contract provides no source-backed idempotency key,
strong-consistency guarantee, or bounded quiescence rule that would let the
supervisor distinguish a rejected launch from an accepted-but-not-yet-visible launch.
After a send with an unknown outcome, one zero-result list response therefore cannot
prove that no billable instance exists. An accepted instance could be both
unidentifiable and unterminable under the proposed exact-ID-only cleanup rule.

That source gap alone requires `blocked-human-or-source-decision`. It may not be
replaced by inference, replay, broader account mutation, name-based guessing, or a
claim of exactly-once network behavior.

## Independent control-plane blockers

The review also found that the repository has useful local draft primitives but no
single authoritative supervisor that enforces all of the following end to end:

1. exact authorization, clean commit, plan, run, operation order, cardinality,
   spacing, aggregate call/byte/wall/cost caps, and irreversible no-replay state;
2. endpoint-specific response-schema and semantic validation before state advances;
3. a bounded SSH/keyscan process executor with held path identities, an exclusive
   run-owned `known_hosts`, output/deadline counters, and no arbitrary path injection;
4. allowlisted projection of provider and process outputs so Jupyter credentials,
   unrelated account data, and unrelated command lines cannot enter evidence;
5. success/incident evidence eligibility that requires a complete provider ledger,
   authorization/implementation bindings, detailed OS/kernel/cgroup/Docker/container
   identities, process evidence, termination, cleanup, and incident disposition;
6. archive copy and postflight verification that remain bound to held no-follow
   descriptors rather than reopening the destination by pathname.

Mocks validate draft functions only. They do not prove provider visibility,
termination or billing, SSH reachability, kernel containment, Docker behavior, or
external-volume durability.

## Privacy adjudication

The current public copy of
`docs/harness/evidence/T07_RUN_0003_POSTRUN_ADJUDICATION.json` no longer retains local
SSH fingerprints or local key paths. Its current SHA-256 is
`23ae723811cb15b2cbc1229592d507624c9107851fc883d9ce023464301631d0`.
The original Git object remains preserved at starting commit
`314270ecd27115d801ea6348ac7653d30d56a884`, where the file hash was
`95b08f6e9345aa09ba4b81dcb6b70484ca0a4d2a964cc553f2a3ae4fe96ee782`.
No ignored or externally sealed evidence was rewritten.

## Numeric decision inputs and rejected draft limits

The human decision validly supplied a USD 2.00 aggregate provider ceiling, a
3,600-second provider wall, and a 600-second host-key checkpoint inside that wall.
The observed one-hour list cost is USD 1.29. These are private-decision constraints,
not executable caps.

No aggregate Gate L2 call, byte, process, SSH, container, archive, or storage cap is
issued because there is no enforceable supervisor or executable plan. Values derived
in the rejected draft remain non-authoritative test inputs and cannot be copied into
an authorization.

## Terminal decision

`blocked-human-or-source-decision`

There is no executable plan ID, path, byte count, SHA-256, or ready-to-copy
authorization block. The proposed V1 plan/run identities are rejected and
non-reusable. Progress requires both a source-backed solution to launch-outcome
ambiguity and a new reviewed end-to-end supervisor/evidence implementation, followed
by a fresh plan and a fresh user authorization. This turn does not create another
design gate or select a workaround.

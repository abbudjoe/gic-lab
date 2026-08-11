# T07 Gate L2M manual-console decision packet

Status: **blocked-human-image-selection; no execution authority**

Date: 2026-08-10

## Required human decision

The existing private decision selects `img-0111` / `gpu-base-22-04` /
`22.4.5-2141`. Lambda's current first-party image table documents Docker but not
JupyterLab for GPU Base. The proposed Jupyter-only topology therefore requires a new
explicit image choice.

Recommended replacement:

```text
alias: img-0032
family: lambda-stack-22-04
version: 22.4.5-2141
region: us-east-1
architecture: x86_64
Python: 3.10
documented: Docker + JupyterLab
```

Alternates, newest first, are `img-0106` / `22.4.5-1722`, `img-0037` /
`22.4.5-1459`, and `img-0012` / `22.4.5-1026`. Raw image IDs remain private.
These are x86-64 Lambda Stack candidates with `us-east-1` availability. The pinned
sources do not expose a `gpu_1x_a10`→image compatibility matrix, so a future run must
confirm the approved alias/version is actually offered after selecting the exact type
and region, attest that fact in the launch checkpoint, and stop before Launch without
substitution if it is absent.

## Private decision contract

The user must decide whether to approve all of the following together:

1. change the image to recommended `img-0032` / `22.4.5-2141`;
2. use the sealed unique `fractal-lambda-codex` key for launch-wizard satisfaction
   only, with zero SSH use in Gate L2M;
3. manually replace the global firewall with one private TCP/22 `/32` rule;
4. manually create one fresh `us-east-1` per-instance ruleset with the same sole rule;
5. manually click Launch exactly once for `gpu_1x_a10`, `us-east-1`, the approved
   image, no filesystem, that key, and that ruleset;
6. use only Cloud IDE/Jupyter for host qualification;
7. manually terminate, delete the owned ruleset, and restore the original global
   rules in the required order;
8. attest no other workspace resource needs the current global rules, no other actor
   will mutate Lambda account instances during the exclusive T07 window, and remain
   present for the entire billable window;
9. acknowledge that console/control-plane outage can extend billing; and
10. bind a private current public IPv4 `/32`, 32 random nonce bytes, USD 2.00,
    3,600 seconds, and 300 seconds per user checkpoint.

The future private path is
`~/.config/gic-lab/t07/l2-manual-console-decisions.json`, current-user owned,
mode `0600`, single-link, regular, and opened no-follow. Do not put its contents in
chat or Git.

- Schema: `schemas/t07-lambda-l2m-human-decision.schema.json`, 3,183 bytes,
  SHA-256 `7054b83d9aa56683b24ba3c1057ca6f9aeb9ae1ee38fc3d2f37179514d4f1d79`.
- Deliberately invalid template:
  `containers/sira-smoke/lambda/manual-console/T07_L2M_HUMAN_DECISION_TEMPLATE.json`,
  1,479 bytes, SHA-256
  `a728ed2365c07ce2de97ddff97555770123379485d071df8c123b42181e5e795`.

The template is not an authorization and must remain invalid in Git. This turn did not
create the user's private file.

## Current disposition

There is no manual plan ID, run ID, plan path, byte count, SHA-256, execution commit,
or ready-to-copy authorization block. The image decision above is the unresolved
blocking human choice. Even after it is made, a later offline materialization/review
must bind its private hash, fresh marker, current clean commit, current price/capacity,
zero running instances, exact source and bundle hashes, fresh paths, checkpoints,
storage floors, and an exact current-turn authorization before any console mutation.

Cloud mutation, paid compute, provider secret access, SSH, Jupyter, containers,
browsers, model calls, SiRA, scientific execution, Gate L3, and Gate L4 remain false.
